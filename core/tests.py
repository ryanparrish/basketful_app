"""Tests for order window functionality."""
from django.test import TestCase
from apps.account.models import Participant
from apps.lifeskills.models import Program
from core.models import OrderWindowSettings
from core.utils import can_place_order, get_next_class_datetime


class OrderWindowTestCase(TestCase):
    """Test order window restrictions."""

    def setUp(self):
        """Set up test data."""
        # Create a program with Wednesday class at 2:00 PM
        self.program = Program.objects.create(
            name="Test Program",
            MeetingDay="wednesday",
            meeting_time="14:00:00",
            meeting_address="123 Test St"
        )

        # Create participant
        self.participant = Participant.objects.create(
            name="Test Participant",
            email="test@example.com",
            program=self.program
        )

        # Ensure settings exist
        self.settings = OrderWindowSettings.get_settings()
        self.settings.enabled = True
        self.settings.hours_before_class = 24
        self.settings.save()

    def test_settings_singleton(self):
        """Test that only one OrderWindowSettings instance exists."""
        settings1 = OrderWindowSettings.get_settings()
        settings2 = OrderWindowSettings.get_settings()
        self.assertEqual(settings1.pk, settings2.pk)

    def test_get_next_class_datetime(self):
        """Test calculation of next class datetime."""
        next_class = get_next_class_datetime(self.participant)
        self.assertIsNotNone(next_class)
        # Should be a Wednesday
        self.assertEqual(next_class.weekday(), 2)  # 2 = Wednesday
        # Should be at 2:00 PM
        self.assertEqual(next_class.hour, 14)
        self.assertEqual(next_class.minute, 0)

    def test_can_place_order_window_disabled(self):
        """Test that orders are allowed when window is disabled."""
        self.settings.enabled = False
        self.settings.save()

        can_order, context = can_place_order(self.participant)
        self.assertTrue(can_order)
        self.assertFalse(context['window_enabled'])

    def test_can_place_order_no_program(self):
        """Test that orders are blocked when no program assigned."""
        self.participant.program = None
        self.participant.save()

        can_order, context = can_place_order(self.participant)
        self.assertFalse(can_order)
        self.assertIsNone(context['next_class'])

    def test_order_window_context(self):
        """Test that order window context is correctly populated."""
        _can_order, context = can_place_order(self.participant)

        self.assertIn('window_enabled', context)
        self.assertIn('next_class', context)
        self.assertIn('window_opens', context)
        self.assertIn('hours_before_class', context)

        if context['next_class']:
            self.assertEqual(
                context['hours_before_class'],
                self.settings.hours_before_class
            )

    def test_settings_validation(self):
        """Test settings field validation."""
        # Test min/max validators
        self.settings.hours_before_class = 24
        self.settings.full_clean()  # Should not raise

        # Hours should be between 1 and 168
        self.settings.hours_before_class = 1
        self.settings.full_clean()  # Should not raise

        self.settings.hours_before_class = 168
        self.settings.full_clean()  # Should not raise

