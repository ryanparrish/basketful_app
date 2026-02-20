"""Utility functions for managing program pause voucher states."""
import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def set_voucher_pause_state(voucher_ids, activate=False, multiplier=1):
    """
    Set pause state on vouchers in an idempotent, transactional way.
    
    Args:
        voucher_ids (list): List of voucher IDs to update
        activate (bool): True to flag vouchers, False to clear flags
        multiplier (int): Multiplier to apply when activating (default 1)
        
    Returns:
        tuple: (updated_count, skipped_count)
    """
    from apps.voucher.models import Voucher
    
    if not voucher_ids:
        logger.info("[Voucher State] No voucher IDs provided")
        return (0, 0)
    
    # Ensure list
    if isinstance(voucher_ids, int):
        voucher_ids = [voucher_ids]
    elif not hasattr(voucher_ids, '__iter__'):
        voucher_ids = list(voucher_ids)
    
    target_flag = activate
    target_multiplier = multiplier if activate else 1
    
    updated_count = 0
    skipped_count = 0
    
    with transaction.atomic():
        vouchers = Voucher.objects.filter(id__in=voucher_ids).select_for_update()
        
        for voucher in vouchers:
            # Check if already in target state (idempotent)
            if (
                voucher.program_pause_flag == target_flag
                and voucher.multiplier == target_multiplier
            ):
                skipped_count += 1
                continue
            
            # Update to target state
            voucher.program_pause_flag = target_flag
            voucher.multiplier = target_multiplier
            voucher.save(update_fields=['program_pause_flag', 'multiplier'])
            updated_count += 1
    
    # Log results
    action = "activated" if activate else "cleared"
    if updated_count > 0:
        logger.info(
            "[Voucher State] %s %d vouchers (multiplier=%d), skipped %d already correct",
            action.capitalize(),
            updated_count,
            target_multiplier,
            skipped_count
        )
    elif skipped_count > 0:
        logger.info(
            "[Voucher State] All %d vouchers already %s (idempotent)",
            skipped_count,
            action
        )
    
    return (updated_count, skipped_count)
