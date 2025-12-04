"""Utility functions for order window checking."""
from datetime import datetime, timedelta, time
from django.utils import timezone


def get_next_class_datetime(participant):
    """
    Calculate the next class datetime for a participant.
    
    Args:
        participant: Participant instance with program
        
    Returns:
        datetime: Next class datetime in participant's timezone, or None
    """
    if not participant.program:
        return None
    
    program = participant.program
    meeting_day = program.MeetingDay.lower()
    meeting_time = program.meeting_time
    
    # Convert meeting_time to time object if it's a string
    if isinstance(meeting_time, str):
        from datetime import time as datetime_time
        hour, minute, second = meeting_time.split(':')
        meeting_time = datetime_time(
            int(hour), int(minute), int(second.split('.')[0])
        )
    
    # Map day names to weekday integers (0=Monday, 6=Sunday)
    day_mapping = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
    }
    
    target_weekday = day_mapping.get(meeting_day)
    if target_weekday is None:
        return None
    
    # Get current time
    now = timezone.now()
    current_weekday = now.weekday()
    
    # Calculate days until next meeting
    days_ahead = target_weekday - current_weekday
    
    # If target day is today or has passed this week, move to next week
    if days_ahead < 0:  # Target day already passed this week
        days_ahead += 7
    
    # Create datetime for next class
    next_class_date = now.date() + timedelta(days=days_ahead)
    next_class_datetime = timezone.make_aware(
        datetime.combine(next_class_date, meeting_time)
    )
    
    # If the class is today but the time has already passed, move to next week
    if days_ahead == 0 and next_class_datetime <= now:
        next_class_datetime += timedelta(days=7)
    
    return next_class_datetime


def can_place_order(participant):
    """
    Check if participant is within their order window.
    
    Args:
        participant: Participant instance
        
    Returns:
        tuple: (bool: can_order, dict: context with timing info)
    """
    from core.models import OrderWindowSettings
    
    settings = OrderWindowSettings.get_settings()
    
    # If order window is disabled, always allow orders
    if not settings.enabled:
        return True, {
            'window_enabled': False,
            'next_class': None,
            'window_opens': None,
            'hours_remaining': None
        }
    
    next_class = get_next_class_datetime(participant)
    
    # If no program assigned, don't allow orders
    if next_class is None:
        return False, {
            'window_enabled': True,
            'next_class': None,
            'window_opens': None,
            'hours_remaining': None,
            'reason': 'No program assigned'
        }
    
    # Calculate when order window opens and closes
    window_opens = next_class - timedelta(
        hours=settings.hours_before_class
    )
    window_closes = next_class - timedelta(
        hours=settings.hours_before_close
    )
    now = timezone.now()
    
    # Check if we're in the order window
    can_order = window_opens <= now < window_closes
    
    # Calculate hours until window opens or closes
    hours_until_open = None
    hours_until_close = None
    
    if now < window_opens:
        time_diff = window_opens - now
        hours_until_open = time_diff.total_seconds() / 3600
    elif now < window_closes:
        time_diff = window_closes - now
        hours_until_close = time_diff.total_seconds() / 3600
    
    return can_order, {
        'window_enabled': True,
        'next_class': next_class,
        'window_opens': window_opens,
        'window_closes': window_closes,
        'hours_until_open': hours_until_open,
        'hours_until_close': hours_until_close,
        'hours_before_class': settings.hours_before_class,
        'hours_before_close': settings.hours_before_close,
        'can_order': can_order
    }
