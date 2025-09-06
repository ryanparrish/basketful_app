from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from random import choice

from .models import CombinedOrder, Order, Program, EmailLog

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
        reply_to="support@loveyourneighbor.org"
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
        reply_to="it@loveyourneighbor.org"
    )
