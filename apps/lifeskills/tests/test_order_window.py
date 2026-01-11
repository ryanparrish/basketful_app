"""Integration test for order window in participant dashboard."""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program
from core.models import OrderWindowSettings


class ParticipantDashboardOrderWindowTest(TestCase):
    """Test order window integration in participant dashboard."""

    def setUp(self):
        """Set up test data."""
        # Create program
        self.program = Program.objects.create(
            name="Wednesday Program",
            MeetingDay="wednesday",
            meeting_time="14:00:00",
            meeting_address="123 Test St"
        )

        # Create user and participant
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',  # noqa: S106
            first_name='Test'
        )
        
        self.participant = Participant.objects.create(
            name="Test User",
            email="test@example.com",
            program=self.program,
            user=self.user
        )

        # Get or create account balance (might be created by signal)
        self.account, _ = AccountBalance.objects.get_or_create(
            participant=self.participant
        )

        # Set up order window settings
        self.settings = OrderWindowSettings.get_settings()
        self.settings.enabled = True
        self.settings.hours_before_class = 24
        self.settings.save()

        self.client = Client()

    def test_dashboard_loads_with_order_window_context(self):
        """Test dashboard loads and includes order window context."""
        self.client.login(
            username='testuser',
            password='testpass123'  # noqa: S106
        )
        response = self.client.get('/dashboard/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('can_order', response.context)
        self.assertIn('order_window', response.context)
        
        # Verify order window context structure
        order_window = response.context['order_window']
        self.assertIn('window_enabled', order_window)
        self.assertIn('next_class', order_window)
        
    def test_dashboard_when_window_disabled(self):
        """Test dashboard when order window is disabled."""
        self.settings.enabled = False
        self.settings.save()
        
        self.client.login(
            username='testuser',
            password='testpass123'  # noqa: S106
        )
        response = self.client.get('/dashboard/')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_order'])
        self.assertFalse(
            response.context['order_window']['window_enabled']
        )
    
    def test_dashboard_participant_no_program(self):
        """Test dashboard when participant has no program."""
        self.participant.program = None
        self.participant.save()
        
        self.client.login(
            username='testuser',
            password='testpass123'  # noqa: S106
        )
        response = self.client.get('/dashboard/')
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_order'])
        self.assertIsNone(
            response.context['order_window']['next_class']
        )
