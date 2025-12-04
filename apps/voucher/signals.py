from django.db.models.signals import (
    pre_save,
    post_save,
    pre_delete,
    post_delete,
)
from django.dispatch import receiver

from apps.voucher.models import Voucher
from apps.log.logging import log_voucher


@receiver(pre_save, sender=Voucher)
def voucher_pre_save(instance, **kwargs):
    """Capture balance and state before creating/updating a voucher."""
    instance._balance_before = instance.account.full_balance
    
    # Capture previous state for comparison
    if instance.pk:
        try:
            old_instance = Voucher.objects.get(pk=instance.pk)
            instance._state_before = old_instance.state
            instance._active_before = old_instance.active
        except Voucher.DoesNotExist:
            instance._state_before = None
            instance._active_before = None
    else:
        instance._state_before = None
        instance._active_before = None


@receiver(post_save, sender=Voucher)
def voucher_post_save(instance, created, **kwargs):
    """Log after a voucher is created or updated."""
    balance_after = instance.account.full_balance
    
    if created:
        log_voucher(
            message=(
                f"Voucher {instance.id} of type '{instance.voucher_type}' "
                f"CREATED for account {instance.account}. "
                f"State: {instance.state}, Active: {instance.active}"
            ),
            log_type='INFO',
            voucher=instance,
            balance_before=getattr(instance, '_balance_before', None),
            balance_after=balance_after
        )
    else:
        # Log state changes
        state_before = getattr(instance, '_state_before', None)
        active_before = getattr(instance, '_active_before', None)
        
        changes = []
        if state_before and state_before != instance.state:
            changes.append(f"state: {state_before} → {instance.state}")
        
        if active_before is not None and active_before != instance.active:
            changes.append(
                f"active: {active_before} → {instance.active}"
            )
        
        if changes:
            log_voucher(
                message=(
                    f"Voucher {instance.id} UPDATED: "
                    f"{', '.join(changes)}"
                ),
                log_type='INFO',
                voucher=instance,
                balance_before=getattr(instance, '_balance_before', None),
                balance_after=balance_after
            )


@receiver(pre_delete, sender=Voucher)
def voucher_pre_delete(instance, **kwargs):
    """Capture balance before deleting a voucher."""
    instance._balance_before = instance.account.full_balance()


@receiver(post_delete, sender=Voucher)
def voucher_post_delete(instance, **kwargs):
    """Log after a voucher is deleted."""
    balance_after = instance.account.full_balance
    log_voucher(
        message=(
            f"Voucher {instance.id} of type '{instance.voucher_type}' "
            f"DELETED from account {instance.account}."
        ),
        log_type='WARNING',
        voucher=instance,
        balance_before=getattr(instance, '_balance_before', None),
        balance_after=balance_after
    )
