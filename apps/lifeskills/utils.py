"""Program pause helpers: EST dates and the live pause multiplier."""
import zoneinfo
from django.utils import timezone


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


def active_pause():
    """
    The live (non-archived) pause in its double-week window, or None.

    This is the single source of truth for "are we in a double week, and
    which pause?" Balance, category limits, order creation, the admin
    voucher screens and failed-order audits all read it; nothing stores a
    copy (#141).

    A pause is in its window 10-14 EST days before it starts (see
    ProgramPause.is_active_gate). If two pauses overlap, the higher
    multiplier wins, then the earlier start.
    """
    from apps.lifeskills.models import ProgramPause

    # The default manager excludes archived pauses; the table stays small.
    live_pauses = ProgramPause.objects.order_by('pause_start', 'id')
    gated_pauses = [pause for pause in live_pauses if pause.is_active_gate]
    return max(gated_pauses, key=lambda pause: pause.multiplier, default=None)


def current_pause_multiplier() -> int:
    """The live pause multiplier: 2 or 3 during a double week, else 1."""
    pause = active_pause()
    return pause.multiplier if pause else 1
