# account/signals.py
"""Signals for account-related models."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Participant  # Import the Participant model


@receiver(post_save, sender=Participant)
def update_base_balance_on_change(instance, created, **kwargs):
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
            "Triggering onboarding email for participant-linked user %s",
            instance.user.id,
        )
        send_new_user_onboarding_email.delay(user_id=instance.user.id)
       