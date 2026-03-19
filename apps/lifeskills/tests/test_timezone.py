"""Tests for timezone-specific date calculations in program pause logic."""
import pytest
from freezegun import freeze_time
from datetime import timedelta
from django.utils import timezone

from apps.lifeskills.utils import get_est_date
from apps.lifeskills.models import ProgramPause


class TestGetEstDate:
    """Test the EST date conversion helper."""
    
    @freeze_time("2026-03-18 03:00:00")  # UTC 3 AM
    def test_utc_early_morning_converts_to_previous_est_day(self):
        """
        When it's 3 AM UTC, it's 11 PM EST the previous day.
        Ensure we get the correct EST date.
        """
        utc_now = timezone.now()
        est_date = get_est_date(utc_now)
        
        # 2026-03-18 03:00 UTC = 2026-03-17 23:00 EST (previous day)
        assert est_date.year == 2026
        assert est_date.month == 3
        assert est_date.day == 17  # Previous day
    
    @freeze_time("2026-03-18 12:00:00")  # UTC noon
    def test_utc_daytime_matches_est_day(self):
        """During UTC daytime, EST date should match."""
        utc_now = timezone.now()
        est_date = get_est_date(utc_now)
        
        # 2026-03-18 12:00 UTC = 2026-03-18 07:00 EST (same day)
        assert est_date.year == 2026
        assert est_date.month == 3
        assert est_date.day == 18  # Same day
    
    def test_no_argument_uses_current_time(self):
        """When no datetime provided, should use current time."""
        est_date = get_est_date()
        assert est_date is not None


@pytest.mark.django_db
class TestProgramPauseWithTimezone:
    """Test program pause calculations with timezone awareness."""
    
    @freeze_time("2026-02-10 03:00:00")  # UTC 3 AM = EST Feb 9, 11 PM
    def test_ordering_window_detection_near_midnight_utc(self):
        """
        Verify ordering window uses EST date, not UTC date.
        
        Scenario:
        - UTC: Feb 10, 3 AM
        - EST: Feb 9, 11 PM
        - Pause start: Feb 21 (EST)
        - Days until start should be 12 (Feb 9 to Feb 21), not 11
        """
        # Create pause 12 days from EST Feb 9
        pause_start = timezone.now() + timedelta(days=12)
        pause_end = pause_start + timedelta(days=7)
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Test midnight"
        )
        
        multiplier, _ = pp._calculate_pause_status()
        
        # Should be in 11-14 day window (12 days away in EST)
        assert multiplier > 1, "Should be in ordering window"
        assert pp.is_active_gate is True, "Pause should be active"
    
    @freeze_time("2026-02-10 12:00:00")  # UTC noon
    def test_ordering_window_detection_during_day(self):
        """
        Verify calculation works correctly during daytime hours.
        
        Scenario:
        - UTC: Feb 10, noon
        - EST: Feb 10, 7 AM
        - Pause start: Feb 22 (EST)
        - Days until start: 12 days
        """
        pause_start = timezone.now() + timedelta(days=12)
        pause_end = pause_start + timedelta(days=7)
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Test daytime"
        )
        
        multiplier, _ = pp._calculate_pause_status()
        assert multiplier > 1, "Should be in ordering window"
        assert pp.is_active_gate is True, "Pause should be active"
    
    @freeze_time("2026-03-18 03:00:00")  # UTC 3 AM
    def test_production_scenario_11_days_away(self):
        """
        Test the actual production scenario from the bug report.
        
        Scenario:
        - UTC: March 18, 3 AM (production shows March 19)
        - EST: March 17, 11 PM
        - Pause start: March 29
        - Days until start: 12 days in EST, should show as active
        """
        # Pause starts March 29
        from datetime import datetime
        pause_start = timezone.make_aware(datetime(2026, 3, 29, 6, 0, 0))  # 6 AM UTC = 1 AM EST
        pause_end = pause_start + timedelta(days=14)
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Easter and Spring Break"
        )
        
        # Get EST dates for verification
        today_est = get_est_date()
        pause_start_est = get_est_date(pause_start)
        days_until = (pause_start_est - today_est).days
        
        # Should be within 11-14 day window
        assert 11 <= days_until <= 14, f"Expected 11-14 days, got {days_until}"
        
        multiplier, _ = pp._calculate_pause_status()
        assert multiplier > 1, f"Should be in ordering window, multiplier={multiplier}"
        assert pp.is_active_gate is True, "Pause should show as active, not upcoming"
    
    @freeze_time("2026-02-10 03:00:00")
    def test_outside_window_too_close(self):
        """
        Test pause that's too close (10 days away).
        Should NOT be in ordering window.
        """
        pause_start = timezone.now() + timedelta(days=10)
        pause_end = pause_start + timedelta(days=7)
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Too close"
        )
        
        multiplier, _ = pp._calculate_pause_status()
        assert multiplier == 1, "Should NOT be in ordering window (too close)"
        assert pp.is_active_gate is False
    
    @freeze_time("2026-02-10 03:00:00")
    def test_outside_window_too_far(self):
        """
        Test pause that's too far (15 days away).
        Should NOT be in ordering window.
        """
        pause_start = timezone.now() + timedelta(days=15)
        pause_end = pause_start + timedelta(days=7)
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Too far"
        )
        
        multiplier, _ = pp._calculate_pause_status()
        assert multiplier == 1, "Should NOT be in ordering window (too far)"
        assert pp.is_active_gate is False
    
    @freeze_time("2026-02-10 03:00:00")
    def test_extended_pause_multiplier_3(self):
        """Test that extended pause (>=14 days) gets multiplier 3."""
        pause_start = timezone.now() + timedelta(days=12)
        pause_end = pause_start + timedelta(days=14)  # 14 day pause
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Extended pause"
        )
        
        multiplier, message = pp._calculate_pause_status()
        assert multiplier == 3, "Extended pause should have multiplier 3"
        assert "Extended pause" in message
    
    @freeze_time("2026-02-10 03:00:00")
    def test_short_pause_multiplier_2(self):
        """Test that short pause (<14 days) gets multiplier 2."""
        pause_start = timezone.now() + timedelta(days=12)
        pause_end = pause_start + timedelta(days=7)  # 7 day pause
        
        pp = ProgramPause.objects.create(
            pause_start=pause_start,
            pause_end=pause_end,
            reason="Short pause"
        )
        
        multiplier, message = pp._calculate_pause_status()
        assert multiplier == 2, "Short pause should have multiplier 2"
        assert "Short pause" in message


@pytest.mark.django_db
class TestSignalHandlerTimezone:
    """Test signal handler uses EST for calculations."""
    
    # TODO: Add signal handler test when proper fixtures are available
    # The signal handler correctly uses EST dates via get_est_date()
    # See apps/lifeskills/signals.py lines 53-58 for implementation
    pass
