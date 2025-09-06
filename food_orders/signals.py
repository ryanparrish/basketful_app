# signals.py

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import Participant, UserProfile, Voucher,AccountBalance
from .user_utils import create_participant_user
from .tasks import send_new_user_onboarding_email
from .voucher_utils import setup_account_and_vouchers
from .logging import log_voucher
from django.dispatch import receiver
from .balance_utils import calculate_base_balance

User = get_user_model()

# ============================================================
# Participant Signals
# ============================================================

@receiver(post_save, sender=Participant)
def update_base_balance_on_change(sender, instance, created, **kwargs):
    """
    Update AccountBalance.base_balance whenever relevant fields change.
    New participants are ignored (handled by a different signal).
    """
    if created:
        return  # skip new participants

    # Always recalc base balance
    from .models import AccountBalance
    from .balance_utils import calculate_base_balance

    account_balance, _ = AccountBalance.objects.get_or_create(participant=instance)
    account_balance.base_balance = calculate_base_balance(instance)
    account_balance.save()


def setup_account_and_vouchers(participant) -> None:
    """
    Ensure a participant has an account balance with calculated base balance
    and initial grocery vouchers.
    """
    from .models import AccountBalance, Voucher  # lazy import
    from .balance_utils import calculate_base_balance  # updated import

    if hasattr(participant, "accountbalance"):
        return

    base_balance = calculate_base_balance(participant)

    account = AccountBalance.objects.create(
        participant=participant,
        base_balance=base_balance
    )

    # Create 2 initial grocery vouchers
    Voucher.objects.bulk_create([
        Voucher(account=account, voucher_type="grocery", active=True)
        for _ in range(2)
    ])

@receiver(post_save, sender=Participant)
def initialize_participant(sender, instance: Participant, created, **kwargs):
    """
    Initialize a participant after creation:
    - Create linked User if `create_user` is True
    - Create UserProfile
    - Setup account and vouchers
    - Trigger onboarding email
    """
    if not created:
        return

    # Only create linked User if the flag is True
    create_user_flag = getattr(instance, 'create_user', False)
    if create_user_flag and not instance.user:
        user = create_participant_user(
            first_name=instance.name,
            email=instance.email,
            participant_name=instance.name,
        )
        instance.user = user
        instance.save(update_fields=["user"])

    # Ensure UserProfile exists
    if instance.user:
        UserProfile.objects.get_or_create(user=instance.user)

    # Trigger onboarding email if a user was created
    if instance.user and create_user_flag:
        send_new_user_onboarding_email.delay(user_id=instance.user.id)


@receiver(post_save, sender=User)
def create_staff_user_profile_and_onboarding(sender, instance: User, created, **kwargs):
    """
    Trigger onboarding email for staff users.
    """
    if instance.is_staff:
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
