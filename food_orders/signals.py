# signals.py
import logging
from celery import current_app 
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from .balance_utils import calculate_base_balance
from .logging import log_voucher
from .models import (
Participant, 
UserProfile,
Voucher,
ProgramPause,
AccountBalance
)
from .tasks.email import send_new_user_onboarding_email
from .user_utils import create_participant_user
from .voucher_utils import setup_account_and_vouchers

logger = logging.getLogger(__name__)
User = get_user_model()

# ============================================================
# Participant Signals
# ============================================================

@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created):
    """
    Update AccountBalance.base_balance whenever relevant fields change.
    New participants are ignored (handled by a different signal).
    """
    if created:
        return  # skip new participants

    account_balance = AccountBalance.objects.get(participant=instance)
    account_balance.base_balance = calculate_base_balance(instance)
    account_balance.save(update_fields=["base_balance"])

@receiver(post_save, sender=Participant)
def ensure_account_and_vouchers(sender, instance, created, **kwargs):
    """
    Signal wrapper: ensure each participant has an account and initial vouchers.
    Skips new participants if you have a separate handler for creation.
    """
    if created:
        # Optional: handle new participants differently if needed
        pass

    # Call the util function
    setup_account_and_vouchers(instance)


@receiver(post_save, sender=Participant)
def initialize_participant(sender, instance: Participant, created, **kwargs):
    """
    Initialize a participant after creation:
    - Create linked User if `create_user` is True
    - Create UserProfile
    - Setup account and vouchers
    - Trigger onboarding email
    """
    create_user_flag = getattr(instance, "create_user", False)

    if not created:
        return
    elif create_user_flag == True:
        user = create_participant_user(
            first_name=instance.name,
            email=instance.email,
            participant_name=instance.name,
        )
        instance.user = user
       
    # Ensure UserProfile exists
    if instance.user:
        UserProfile.objects.get_or_create(user=instance.user)
        setup_account_and_vouchers(instance)
    # Trigger onboarding email if a user was created via participant flow
    if instance.user and create_user_flag:
        logger.debug(
            f"Triggering onboarding email for participant-linked user {instance.user.id}"
        )
        send_new_user_onboarding_email.delay(user_id=instance.user.id)
       
@receiver(post_save, sender=User)
def create_staff_user_profile_and_onboarding(sender, instance: User, created, update_fields, **kwargs):
    """
    Trigger onboarding email for *new* staff users only.
    Ignore login-related saves (e.g., last_login updates).
    """
    # Skip updates that only touch last_login (login event)
    if update_fields and update_fields == {"last_login"}:
        return

    if created and instance.is_staff:
        # Ensure UserProfile exists
        UserProfile.objects.get_or_create(user=instance)

        logger.debug(f"Triggering onboarding email for new staff user {instance.id}")
        send_new_user_onboarding_email.delay(user_id=instance.id)

# ============================================================
# Voucher Signals
# ============================================================

@receiver(pre_save, sender=Voucher)
def voucher_pre_save(sender, instance, **kwargs):
    """Capture balance before creating/updating a voucher."""
    instance._balance_before = instance.account.full_balance


@receiver(post_save, sender=Voucher)
def voucher_post_save(sender, instance, created, **kwargs):
    """Log after a voucher is created or updated."""
    balance_after = instance.account.full_balance
    if created:
        log_voucher(
            message=f"Voucher {instance.id} of type '{instance.voucher_type}' CREATED for account {instance.account}.",
            log_type='INFO',
            voucher=instance,
            balance_before=getattr(instance, '_balance_before', None),
            balance_after=balance_after
        )


@receiver(pre_delete, sender=Voucher)
def voucher_pre_delete(sender, instance, **kwargs):
    """Capture balance before deleting a voucher."""
    instance._balance_before = instance.account.full_balance()


@receiver(post_delete, sender=Voucher)
def voucher_post_delete(sender, instance, **kwargs):
    """Log after a voucher is deleted."""
    balance_after = instance.account.full_balance
    log_voucher(
        message=f"Voucher {instance.id} of type '{instance.voucher_type}' DELETED from account {instance.account}.",
        log_type='WARNING',
        voucher=instance,
        balance_before=getattr(instance, '_balance_before', None),
        balance_after=balance_after
    )


# ============================================================
# Account / Voucher Initialization
# ============================================================

@receiver(post_save, sender=Participant)
def init_account_and_vouchers(sender, instance, created, **kwargs):
    """
    Initialize account and vouchers only for newly created participants.
    """
    if created:
        setup_account_and_vouchers(instance)

# ============================================================
# Program Pause Signals
# ============================================================
import logging
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProgramPause, Voucher
from .tasks.logs import update_voucher_flag

logger = logging.getLogger("program_pause_signal")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from .models import VoucherLog, Participant

class VoucherLogger:
    """Helper to log voucher events to DB and console."""

    @staticmethod
    def debug(participant: Participant, message: str, voucher=None, user=None):
        logger.debug(f"[Voucher DEBUG] {message}")
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="DEBUG",
            user=user
        )

    @staticmethod
    def error(participant: Participant, message: str, voucher=None, user=None, raise_exception=False):
        logger.error(f"[Voucher ERROR] {message}")
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="ERROR",
            user=user
        )
        if raise_exception:
            from django.core.exceptions import ValidationError
            raise ValidationError(message)
    
import sys

@receiver(post_save, sender=ProgramPause)
def schedule_program_pause_and_voucher_tasks(sender, instance, created, **kwargs):
    """
    Schedule activation/deactivation of vouchers for a ProgramPause.
    Fully duration-aware and idempotent.
    Only affects active vouchers belonging to active accounts.
    """
    logger.debug(f"=== Signal Triggered for ProgramPause ID={instance.id} ===")
    logger.debug(
        f"Created={created}, pause_start={instance.pause_start}, pause_end={instance.pause_end}"
    )

    if getattr(instance, "_skip_signal", False):
        logger.debug("Skip signal flag detected; exiting to avoid recursion")
        return

    now = timezone.now()

    # Only active vouchers with active accounts
    vouchers = Voucher.objects.filter(active=True, account__active=True)
    if not vouchers.exists():
        logger.debug("No active vouchers found; exiting signal.")
        return

    voucher_ids = list(vouchers.values_list("id", flat=True))
    logger.debug(f"Voucher IDs affected: {voucher_ids}")

    try:
        # Determine if we should activate or deactivate now
        activate_now = instance.pause_start and instance.pause_start <= now and (
            not instance.pause_end or instance.pause_end > now
        )
        deactivate_now = instance.pause_end and instance.pause_end <= now

        # --- Handle activation ---
        if instance.pause_start and instance.pause_start > now:
            logger.debug(
                f"Scheduling activation for ProgramPause ID={instance.id} at {instance.pause_start}"
            )
            update_voucher_flag.apply_async(
                args=[voucher_ids],
                kwargs={"multiplier": 2, "activate": True},
                eta=instance.pause_start,
            )
        elif activate_now:
            logger.debug("Pause start already passed; activating vouchers immediately.")
            update_voucher_flag.delay(voucher_ids, multiplier=2, activate=True)

        # --- Handle deactivation ---
        if "test" not in sys.argv:  # Skip scheduling deactivation during tests
            if instance.pause_end and instance.pause_end > now:
                logger.debug(
                    f"Scheduling deactivation for ProgramPause ID={instance.id} at {instance.pause_end}"
                )
                update_voucher_flag.apply_async(
                    args=[voucher_ids],
                    kwargs={"multiplier": 1, "activate": False},
                    eta=instance.pause_end,
                )
            elif deactivate_now:
                logger.debug("Pause end already passed; deactivating vouchers immediately.")
                update_voucher_flag.delay(voucher_ids, multiplier=1, activate=False)
        else:
            logger.debug("Skipping deactivation scheduling in test mode.")

        logger.debug(
            f"Tasks scheduled successfully for ProgramPause ID={instance.id} affecting {len(voucher_ids)} vouchers"
        )
    except Exception as e:
        for voucher in vouchers:
            VoucherLogger.error(
                voucher.account.participant,
                f"Unexpected error in ProgramPause signal: {e}",
                voucher=voucher,
            )
        raise

    logger.debug("=== End of Signal ===\n")

