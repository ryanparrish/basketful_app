"""Utility functions for managing program pause voucher states."""
import logging
import zoneinfo
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_est_date(dt=None):
    """
    Convert a datetime to EST/EDT date for consistent day calculation.
    
    ⚠️ WARNING: This function assumes EST (America/New_York) timezone.
    If your organization expands to serve participants in other timezones
    (e.g., PST, MST), this function will need to be refactored to accept
    a timezone parameter or look up the participant/program timezone.
    
    Args:
        dt: datetime object (timezone-aware). If None, uses current time.
        
    Returns:
        date: The date in EST/EDT timezone
        
    Examples:
        >>> # UTC: 2026-03-18 03:00:00 (3 AM) -> EST: 2026-03-17 23:00:00 (11 PM previous day)
        >>> from django.utils import timezone
        >>> from datetime import datetime
        >>> utc_time = timezone.make_aware(datetime(2026, 3, 18, 3, 0))
        >>> get_est_date(utc_time)
        datetime.date(2026, 3, 17)  # Previous day in EST
        
    Future Expansion:
        When adding PST or other timezone support:
        1. Add 'timezone' field to Program model (default='America/New_York')
        2. Update this function to: get_localized_date(dt, tz_string='America/New_York')
        3. Pass program.timezone to all calculation locations
        4. See docs/PROGRAM_PAUSES.md for detailed expansion path
        
    See Also:
        - apps/lifeskills/models.py::ProgramPause._calculate_pause_status()
        - apps/lifeskills/signals.py::handle_program_pause()
        - docs/PROGRAM_PAUSES.md for timezone documentation
    """
    if dt is None:
        dt = timezone.now()
    
    # Convert to EST/EDT (America/New_York handles DST automatically)
    est_tz = zoneinfo.ZoneInfo('America/New_York')
    est_dt = dt.astimezone(est_tz)
    
    return est_dt.date()


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
