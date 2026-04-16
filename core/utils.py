"""Utility functions for order window checking."""
from datetime import datetime, timedelta
from django.utils import timezone


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

WEEKDAY_MAP = {
    'monday': 0,
    'tuesday': 1,
    'wednesday': 2,
    'thursday': 3,
    'friday': 4,
}


def _parse_meeting_time(meeting_time):
    """Normalise meeting_time to a datetime.time object."""
    if isinstance(meeting_time, str):
        from datetime import time as dt_time
        parts = meeting_time.split(':')
        return dt_time(int(parts[0]), int(parts[1]), int(parts[2].split('.')[0]))
    return meeting_time


# ---------------------------------------------------------------------------
# Effective config (COALESCE: per-program override → global singleton)
# ---------------------------------------------------------------------------

def get_effective_config(program) -> dict:
    """
    Return the resolved order-window config for a given Program.

    Each field COALESCEs: if the program has a ProgramOrderWindow row with
    a non-null value that value is used; otherwise we fall back to the global
    OrderWindowSettings singleton.  This preserves 3NF — derived state is
    never stored.

    Returns a dict with keys:
        hours_before_class, hours_before_close, enabled,
        is_overridden,
        hours_before_class_source, hours_before_close_source, enabled_source
        ('program' | 'global' for each source key)
    """
    from core.models import OrderWindowSettings, ProgramOrderWindow

    global_s = OrderWindowSettings.get_settings()

    try:
        ow = program.order_window  # OneToOneField reverse accessor
    except ProgramOrderWindow.DoesNotExist:
        ow = None

    def resolve(field):
        if ow is not None:
            val = getattr(ow, field)
            if val is not None:
                return val, 'program'
        return getattr(global_s, field), 'global'

    hbc, hbc_src = resolve('hours_before_class')
    hbcl, hbcl_src = resolve('hours_before_close')
    en, en_src = resolve('enabled')

    return {
        'hours_before_class': hbc,
        'hours_before_close': hbcl,
        'enabled': en,
        'is_overridden': ow is not None,
        'hours_before_class_source': hbc_src,
        'hours_before_close_source': hbcl_src,
        'enabled_source': en_src,
    }


# ---------------------------------------------------------------------------
# Window cycle generator — pure function, nothing stored
# ---------------------------------------------------------------------------

def generate_window_cycles(program, config: dict, n: int = 3) -> list:
    """
    Generate the next *n* order-window cycles for a program.

    A "cycle" is one (opens_at, closes_at, meeting_at) triplet derived
    purely from the program's MeetingDay + meeting_time and the resolved
    config.  Nothing is written to the database.

    Args:
        program:  lifeskills.Program instance
        config:   result of get_effective_config(program)
        n:        number of upcoming cycles to return (default 3)

    Returns:
        list of dicts with keys: opens_at, closes_at, meeting_at (all aware datetimes)
    """
    meeting_day = program.MeetingDay.lower()
    meeting_time = _parse_meeting_time(program.meeting_time)

    target_weekday = WEEKDAY_MAP.get(meeting_day)
    if target_weekday is None:
        return []

    now = timezone.now()
    current_weekday = now.weekday()

    days_ahead = (target_weekday - current_weekday) % 7
    if days_ahead == 0:
        candidate = now.replace(
            hour=meeting_time.hour,
            minute=meeting_time.minute,
            second=0,
            microsecond=0,
        )
        opens_candidate = candidate - timedelta(hours=config['hours_before_class'])
        if opens_candidate <= now and now >= candidate:
            days_ahead = 7

    base_date = now.date() + timedelta(days=days_ahead)
    base_meeting = timezone.make_aware(
        datetime.combine(base_date, meeting_time)
    )

    cycles = []
    for i in range(n):
        meeting_at = base_meeting + timedelta(weeks=i)
        opens_at = meeting_at - timedelta(hours=config['hours_before_class'])
        closes_at = meeting_at - timedelta(hours=config['hours_before_close'])
        cycles.append({
            'meeting_at': meeting_at,
            'opens_at': opens_at,
            'closes_at': closes_at,
        })
    return cycles


# ---------------------------------------------------------------------------
# Full status snapshot for one program (used by the dashboard endpoint)
# ---------------------------------------------------------------------------

def get_program_window_status(program) -> dict:
    """
    Compute the complete order-window status for a single program.

    Checks for an active ProgramWindowOverride first; if one exists and
    has not expired it governs the status.  Expired overrides are lazily
    deleted here (Celery nightly task handles bulk cleanup).
    """
    from core.models import ProgramWindowOverride

    config = get_effective_config(program)
    now = timezone.now()

    active_override = None
    try:
        ov = program.window_override
        if ov.expires_at > now:
            active_override = ov
        else:
            ov.delete()
    except ProgramWindowOverride.DoesNotExist:
        pass

    if active_override:
        window_status = f'force_{active_override.force_status}'
        seconds_until_change = max(
            0, int((active_override.expires_at - now).total_seconds())
        )
    elif not config['enabled']:
        window_status = 'disabled'
        seconds_until_change = None
    else:
        cycles = generate_window_cycles(program, config, n=1)
        if not cycles:
            window_status = 'no_schedule'
            seconds_until_change = None
        else:
            c = cycles[0]
            if c['opens_at'] <= now < c['closes_at']:
                window_status = 'open'
                seconds_until_change = max(
                    0, int((c['closes_at'] - now).total_seconds())
                )
            else:
                window_status = 'closed'
                seconds_until_change = max(
                    0, int((c['opens_at'] - now).total_seconds())
                )

    try:
        from apps.orders.models import Order
        active_order_count = Order.objects.filter(
            account__participant__program=program,
            status='pending',
        ).count()
    except Exception:
        active_order_count = 0

    return {
        'program_id': program.id,
        'program_name': program.name,
        'meeting_day': program.MeetingDay,
        'meeting_time': str(program.meeting_time),
        'window_status': window_status,
        'cycles': generate_window_cycles(program, config, n=3),
        'seconds_until_change': seconds_until_change,
        'active_order_count': active_order_count,
        'override': active_override,
        'config': config,
    }


# ---------------------------------------------------------------------------
# Legacy: get_next_class_datetime — kept for backwards compatibility
# ---------------------------------------------------------------------------

def get_next_class_datetime(participant):
    """
    Calculate the next class datetime for a participant.

    Args:
        participant: Participant instance with program

    Returns:
        datetime: Next class datetime (aware), or None
    """
    if not participant.program:
        return None

    program = participant.program
    meeting_day = program.MeetingDay.lower()
    meeting_time = _parse_meeting_time(program.meeting_time)

    target_weekday = WEEKDAY_MAP.get(meeting_day)
    if target_weekday is None:
        return None

    now = timezone.now()
    current_weekday = now.weekday()

    days_ahead = target_weekday - current_weekday
    if days_ahead < 0:
        days_ahead += 7

    next_class_date = now.date() + timedelta(days=days_ahead)
    next_class_datetime = timezone.make_aware(
        datetime.combine(next_class_date, meeting_time)
    )

    if days_ahead == 0 and next_class_datetime <= now:
        next_class_datetime += timedelta(days=7)

    return next_class_datetime


# ---------------------------------------------------------------------------
# can_place_order — updated to use per-program effective config + overrides
# ---------------------------------------------------------------------------

def can_place_order(participant):
    """
    Check if a participant is currently within their order window.

    Respects per-program config overrides (ProgramOrderWindow) and active
    manual force-open/close overrides (ProgramWindowOverride).

    Args:
        participant: Participant instance

    Returns:
        tuple: (bool: can_order, dict: context with timing info)
    """
    if not participant.program:
        return False, {
            'window_enabled': True,
            'next_class': None,
            'window_opens': None,
            'hours_remaining': None,
            'reason': 'No program assigned',
        }

    program = participant.program
    config = get_effective_config(program)
    now = timezone.now()

    # --- Check for active manual override first ---
    from core.models import ProgramWindowOverride
    active_override = None
    try:
        ov = program.window_override
        if ov.expires_at > now:
            active_override = ov
        else:
            ov.delete()
    except ProgramWindowOverride.DoesNotExist:
        pass

    if active_override:
        can_order = active_override.force_status == 'open'
        return can_order, {
            'window_enabled': True,
            'next_class': get_next_class_datetime(participant),
            'window_opens': None,
            'window_closes': None,
            'hours_until_open': None,
            'hours_until_close': None,
            'hours_before_class': config['hours_before_class'],
            'hours_before_close': config['hours_before_close'],
            'can_order': can_order,
            'force_override': active_override.force_status,
        }

    # --- No override: check schedule-based window ---
    if not config['enabled']:
        return True, {
            'window_enabled': False,
            'next_class': None,
            'window_opens': None,
            'hours_remaining': None,
        }

    next_class = get_next_class_datetime(participant)
    if next_class is None:
        return False, {
            'window_enabled': True,
            'next_class': None,
            'window_opens': None,
            'hours_remaining': None,
            'reason': 'No program schedule found',
        }

    window_opens = next_class - timedelta(hours=config['hours_before_class'])
    window_closes = next_class - timedelta(hours=config['hours_before_close'])

    can_order = window_opens <= now < window_closes

    hours_until_open = None
    hours_until_close = None
    if now < window_opens:
        hours_until_open = (window_opens - now).total_seconds() / 3600
    elif now < window_closes:
        hours_until_close = (window_closes - now).total_seconds() / 3600

    return can_order, {
        'window_enabled': True,
        'next_class': next_class,
        'window_opens': window_opens,
        'window_closes': window_closes,
        'hours_until_open': hours_until_open,
        'hours_until_close': hours_until_close,
        'hours_before_class': config['hours_before_class'],
        'hours_before_close': config['hours_before_close'],
        'can_order': can_order,
    }
