
@receiver(pre_save, sender=Voucher)
def voucher_pre_save(instance,**kwargs):
    """Capture balance before creating/updating a voucher."""
    instance._balance_before = instance.account.full_balance


@receiver(post_save, sender=Voucher)
def voucher_post_save(instance, created,**kwargs):
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
def voucher_pre_delete(instance,**kwargs):
    """Capture balance before deleting a voucher."""
    instance._balance_before = instance.account.full_balance()

@receiver(post_delete, sender=Voucher)
def voucher_post_delete(instance,**kwargs):
    """Log after a voucher is deleted."""
    balance_after = instance.account.full_balance
    log_voucher(
        message=f"Voucher {instance.id} of type '{instance.voucher_type}' DELETED from account {instance.account}.",
        log_type='WARNING',
        voucher=instance,
        balance_before=getattr(instance, '_balance_before', None),
        balance_after=balance_after
    )
