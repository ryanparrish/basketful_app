# signals.py
import logging
# Django imports
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
# First-party imports
from apps.account.models import UserProfile, Participant
from apps.account.tasks.email import send_new_user_onboarding_email
# Local imports
from .utils.voucher_utils import setup_account_and_vouchers

logger = logging.getLogger("program_pause_signal")
logger.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
User = get_user_model()

# ============================================================
# Participant Signals
# ============================================================


@receiver(post_save, sender=Participant)
def ensure_account_and_vouchers(instance, created, **kwargs):
    """
    Signal wrapper: ensure each participant has an account and initial vouchers.
    Skips new participants if you have a separate handler for creation.
    """
    if created:
        # Optional: handle new participants differently if needed
        pass

    # Call the util function
    setup_account_and_vouchers(instance)


@receiver(post_save, sender=User,)
def create_staff_user_profile_and_onboarding(
    sender, instance: User, created, update_fields, **kwargs
):
    """
    Trigger onboarding email for *new* staff users only.
    Ignore login-related saves (e.g., last_login updates).
    Skip superusers to allow creation without Celery.
    """
    # Skip updates that only touch last_login (login event)
    if update_fields and update_fields == {"last_login"}:
        return

    if created and instance.is_staff:
        # Ensure UserProfile exists
        UserProfile.objects.get_or_create(user=instance)

        # Skip onboarding email for superusers and during testing
        from django.conf import settings
        is_testing = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)
        
        if not instance.is_superuser and not is_testing:
            logger.debug("Triggering onboarding email for new staff user %s", instance.id)
            send_new_user_onboarding_email.delay(user_id=instance.id)


@receiver(post_save, sender=Participant)
def init_account_and_vouchers(sender, instance, created, **kwargs):
    """
    Initialize account and vouchers only for newly created participants.
    """
    if created:
        setup_account_and_vouchers(instance)



