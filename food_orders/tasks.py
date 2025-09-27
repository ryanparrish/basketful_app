# tasks.py

from datetime import timedelta
from random import choice

from celery import shared_task

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from celery import shared_task
from .models import CombinedOrder, EmailLog, Order, Program, ProgramPause, Participant, Voucher
import logging
from celery import shared_task
from django.utils import timezone
import logging
from .models import Voucher, ProgramPause

# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # or DEBUG if you want more detail

# Optional: add a console handler if one doesn’t exist
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

User = get_user_model()

# ---------------------------
# Combined Orders Task
# ---------------------------
@shared_task
def create_weekly_combined_orders():
    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    for program in Program.objects.all():
        # Skip if a weekly parent order already exists
        if CombinedOrder.objects.filter(
            program=program,
            created_at__date__gte=start_of_week,
            created_at__date__lte=end_of_week,
            is_parent=True
        ).exists():
            continue

        weekly_orders = Order.objects.filter(
            account__participant__program=program,
            created_at__date__gte=start_of_week,
            created_at__date__lte=end_of_week
        )

        if not weekly_orders.exists():
            continue

        packers_for_program = program.packers.all()
        selected_packer = choice(packers_for_program) if packers_for_program.exists() else None

        # Step 1: Create individual weekly combined orders
        child_combined_orders = []
        for order in weekly_orders:
            combined_order = CombinedOrder.objects.create(
                program=program,
                packed_by=selected_packer
            )
            combined_order.orders.add(order)
            combined_order.summarized_data = combined_order.summarized_items_by_category()
            combined_order.save(update_fields=['summarized_data'])
            child_combined_orders.append(combined_order)

        # Step 2: Create parent/master combined order that aggregates all child combined orders
        parent_combined_order = CombinedOrder.objects.create(
            program=program,
            packed_by=selected_packer,
            is_parent=True
        )

        # Collect all orders from child combined orders
        all_orders = Order.objects.filter(combined_orders__in=child_combined_orders).distinct()
        parent_combined_order.orders.set(all_orders)
        parent_combined_order.summarized_data = parent_combined_order.summarized_items_by_category()
        parent_combined_order.save(update_fields=['summarized_data'])
    parent_combined_order.save(update_fields=['summarized_data'])

# ---------------------------
# Email Helpers
# ---------------------------

def build_email_context(user):
    """Generate UID and token for emails."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    if getattr(settings, "USE_HTTPS", None) is not None:
        protocol = "https" if settings.USE_HTTPS else "http"
    else:
        protocol = "http" if getattr(settings, "DEBUG", True) else "https"

    domain = settings.DOMAIN_NAME

    return {
        "user": user,
        "domain": domain,
        "uid": uid,
        "token": token,
        "protocol": protocol,
    }

@shared_task
def send_email(user, subject, html_template, text_template, email_type, reply_to=None):
    """
    Sends an email if it hasn't already been sent and logs it in EmailLog.
    """
    if EmailLog.objects.filter(user=user, email_type=email_type).exists():
        return  # prevent duplicates

    context = build_email_context(user)
    html_content = render_to_string(html_template, context)
    text_content = render_to_string(text_template, context)
    from_email = None
    to_email = user.email

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [to_email],
        reply_to=[reply_to] if reply_to else None
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    EmailLog.objects.create(user=user, email_type=email_type)

# ---------------------------
# Onboarding & Password Reset Tasks
# ---------------------------

@shared_task
def send_new_user_onboarding_email(user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    send_email(
        user=user,
        subject="Welcome to Love Your Neighbor!",
        html_template="registration/new_user_onboarding.html",
        text_template="registration/new_user_onboarding.txt",
        email_type="onboarding",
        reply_to="elizabethp@lovewm.org"
    )


@shared_task
def send_password_reset_email(user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    send_email(
        user=user,
        subject="Set Your Password",
        html_template="registration/password_reset_email.html",
        text_template="registration/password_reset_email.txt",
        email_type="password_reset",
        reply_to="elizabethp@lovewm.org"
    )

logger = logging.getLogger(__name__)
@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def update_voucher_flag(self, voucher_ids, multiplier=1, activate=False, program_pause_id=None):
    """
    Idempotent task to update a list of vouchers safely and log changes.

    Args:
        voucher_ids (list[int] or int): IDs of vouchers to update.
        multiplier (int): Multiplier to apply.
        activate (bool): True -> set program_pause_flag, False -> clear it.
        program_pause_id (int): Optional ProgramPause ID for duration validation.
    """
    if not voucher_ids:
        logger.info("[Task] No vouchers to update.")
        return

    # --- Ensure voucher_ids is always iterable ---
    if isinstance(voucher_ids, int):
        voucher_ids = [voucher_ids]
    elif not hasattr(voucher_ids, '__iter__'):
        voucher_ids = list(voucher_ids)

    now = timezone.now()

    # --- Duration check (protects against premature toggles) ---
    if program_pause_id:
        try:
            pp = ProgramPause.objects.get(id=program_pause_id)
        except ProgramPause.DoesNotExist:
            logger.warning(f"[Task] ProgramPause {program_pause_id} not found; skipping duration check.")
            pp = None

        if pp:
            if activate and pp.pause_start and pp.pause_start > now:
                logger.info(
                    f"[Task] Skipping activation for vouchers {voucher_ids}: "
                    f"ProgramPause {pp.id} has not started yet (starts {pp.pause_start}, now={now})."
                )
                return
            if not activate and pp.pause_end and pp.pause_end > now:
                logger.info(
                    f"[Task] Skipping deactivation for vouchers {voucher_ids}: "
                    f"ProgramPause {pp.id} has not ended yet (ends {pp.pause_end}, now={now})."
                )
                return

    try:
        vouchers = Voucher.objects.filter(id__in=voucher_ids)

        for voucher in vouchers:
            target_flag = activate
            target_multiplier = multiplier if activate else 1
            updated_fields = []

            # --- Compare current state vs target state ---
            if voucher.program_pause_flag != target_flag:
                voucher.program_pause_flag = target_flag
                updated_fields.append("program_pause_flag")
            if voucher.multiplier != target_multiplier:
                voucher.multiplier = target_multiplier
                updated_fields.append("multiplier")

            if updated_fields:
                voucher.save(update_fields=updated_fields)
                logger.info(
                    f"[Task] Voucher ID={voucher.id} updated: "
                    f"program_pause_flag={voucher.program_pause_flag}, "
                    f"multiplier={voucher.multiplier}"
                )
            else:
                # --- Explicitly log idempotent skip ---
                logger.info(
                    f"[Task] Voucher ID={voucher.id} already up-to-date. "
                    f"(program_pause_flag={voucher.program_pause_flag}, multiplier={voucher.multiplier})"
                )

    except Exception as exc:
        logger.exception(f"[Task] Error updating vouchers: {voucher_ids}")
        raise self.retry(exc=exc)
