# account/signals.py
"""Signals for account-related models."""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Participant, AccountBalance, UserProfile
from .utils.balance_utils import calculate_base_balance
from .utils.user_utils import create_participant_user
from .tasks.email import send_new_user_onboarding_email
from apps.pantry.utils.voucher_utils import setup_account_and_vouchers

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Participant)
def sync_user_email_on_change(instance: Participant, created, **kwargs):
    """
    Keep User.email in sync with Participant.email whenever it changes.

    Participants authenticate and receive emails via their linked Django User
    account.  Without this sync, changing the email in React Admin (or the
    Django admin) updates only the Participant row, leaving User.email stale
    — so system emails still go to the old address and login with the new
    address fails.

    Skips newly-created participants (User doesn't exist yet at this point;
    initialize_participant handles first-time user creation).
    Also skips participants with no linked user.
    """
    if created:
        return
    if not instance.user_id:
        return

    # Only do the extra UPDATE when email actually differs — avoids a
    # gratuitous write on every unrelated save.
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'email' not in update_fields:
        return

    from django.contrib.auth.models import User as DjangoUser
    try:
        user = instance.user
    except DjangoUser.DoesNotExist:
        return

    if user.email != instance.email:
        user.email = instance.email
        user.save(update_fields=['email'])
        logger.debug(
            "Synced User.email for participant %s (user %s) → %s",
            instance.pk, user.pk, instance.email,
        )


@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created, **kwargs):
    """
    Update AccountBalance.base_balance whenever relevant fields change.
    New participants are ignored (handled by a different signal).
    """
    if created:
        return  # skip new participants
    
    # Skip if update_fields is specified and doesn't include balance-affecting fields
    update_fields = kwargs.get('update_fields')
    if update_fields is not None:
        balance_fields = {'adults', 'children', 'diaper_count'}
        if not balance_fields.intersection(set(update_fields)):
            return  # skip if no balance-affecting fields were updated

    account_balance = AccountBalance.objects.get(participant=instance)
    account_balance.base_balance = calculate_base_balance(instance)
    account_balance.save(update_fields=["base_balance"])


@receiver(post_save, sender=Participant)
def initialize_participant(instance: Participant, created, **kwargs):
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
    elif create_user_flag is True:
        user = create_participant_user(
            first_name=instance.name,
            email=instance.email,
            participant_name=instance.name,
        )
        instance.user = user
        instance.save(update_fields=['user'])
       
    # Ensure UserProfile exists
    if instance.user:
        UserProfile.objects.get_or_create(user=instance.user)
        setup_account_and_vouchers(instance)
    # Trigger onboarding email if a user was created via participant flow
    if instance.user and create_user_flag:
        # When bulk_create sets _skip_onboarding_signal=True it handles the
        # email itself (with an optional grace-period countdown).
        if getattr(instance, '_skip_onboarding_signal', False):
            logger.debug(
                "Skipping onboarding email signal for participant %s "
                "(bulk_create will dispatch with grace period)",
                instance.pk,
            )
        else:
            logger.debug(
                "Triggering onboarding email for participant-linked user %s",
                instance.user.id,
            )
            send_new_user_onboarding_email.delay(user_id=instance.user.id)