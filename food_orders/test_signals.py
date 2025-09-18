from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from .models import (
    AccountBalance,
    Voucher,
    Participant,
    VoucherSetting,
    UserProfile,
    EmailLog,
)
from .balance_utils import calculate_base_balance
from .signals import initialize_participant, create_staff_user_profile_and_onboarding
from .tasks import send_new_user_onboarding_email, send_password_reset_email

User = get_user_model()


class ParticipantSignalsTest(TestCase):
    def setUp(self):
        # Create an active VoucherSetting for all tests
        self.voucher_setting = VoucherSetting.objects.create(
            adult_amount=10,
            child_amount=5,
            infant_modifier=2,
            active=True,
        )

    def create_participant_with_defaults(self, **kwargs):
        """Helper to create a participant with default counts if not provided."""
        defaults = {"adults": 1, "children": 1, "diaper_count": 1}
        defaults.update(kwargs)
        participant = Participant.objects.create(
            name=kwargs.get("name", "Test User"),
            email=kwargs.get("email", "test@test.com"),
            adults=defaults["adults"],
            children=defaults["children"],
            diaper_count=defaults["diaper_count"],
            create_user=kwargs.get("create_user", False),
            user=kwargs.get("user", None),
        )
        return participant

    # ==========================
    # Existing balance/voucher tests
    # ==========================

    def test_account_and_vouchers_created_on_participant_create(self):
        participant = self.create_participant_with_defaults()

        self.assertTrue(hasattr(participant, "accountbalance"))

        vouchers = Voucher.objects.filter(
            account__participant=participant, voucher_type="grocery"
        )
        self.assertEqual(vouchers.count(), 2)

    def test_no_account_created_on_update(self):
        participant = self.create_participant_with_defaults()
        participant.name = "Updated Name"
        participant.save()

        self.assertEqual(
            AccountBalance.objects.filter(participant=participant).count(), 1
        )
        self.assertEqual(
            Voucher.objects.filter(account__participant=participant).count(), 2
        )

    def test_base_balance_updated_on_each_field_change(self):
        participant = self.create_participant_with_defaults()
        account_balance = participant.accountbalance
        initial_balance = account_balance.base_balance

        field_updates = {
            "adults": 3,
            "children": 2,
            "diaper_count": 4,
        }

        for field, new_value in field_updates.items():
            with self.subTest(field=field):
                setattr(participant, field, new_value)
                participant.save()
                account_balance.refresh_from_db()
                self.assertGreater(account_balance.base_balance, initial_balance)
                initial_balance = account_balance.base_balance

    # ==========================
    # Signal tests: initialize_participant
    # ==========================

    def test_initialize_participant_does_nothing_on_update(self):
        participant = self.create_participant_with_defaults()
        post_save.disconnect(initialize_participant, sender=Participant)
        participant.name = "Updated"
        participant.save()
        post_save.connect(initialize_participant, sender=Participant)
        self.assertIsNone(participant.user)

    @patch("food_orders.signals.create_participant_user")  # update path
    def test_initialize_participant_creates_user_and_profile(self, mock_create_user):
        mock_user = User.objects.create(username="mocked")
        mock_create_user.return_value = mock_user

        participant = self.create_participant_with_defaults(
            name="Alice", email="alice@example.com", create_user=True
        )
        participant.refresh_from_db()

        self.assertEqual(participant.user, mock_user)
        self.assertTrue(UserProfile.objects.filter(user=mock_user).exists())

    @patch("food_orders.signals.send_new_user_onboarding_email")  # update path
    @patch("food_orders.signals.create_participant_user")  # update path
    def test_initialize_participant_triggers_onboarding_email(
        self, mock_create_user, mock_send_email
    ):
        mock_user = User.objects.create(username="mocked2")
        mock_create_user.return_value = mock_user

        participant = self.create_participant_with_defaults(
            name="Bob", email="bob@example.com", create_user=True
        )
        participant.refresh_from_db()

        mock_send_email.delay.assert_called_once_with(user_id=mock_user.id)

    def test_initialize_participant_creates_profile_if_user_already_linked(self):
        user = User.objects.create(username="linked")
        participant = self.create_participant_with_defaults(
            name="Charlie", email="c@example.com", user=user, create_user=False
        )
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    # ==========================
    # Signal tests: staff onboarding
    # ==========================

    @patch("food_orders.signals.send_new_user_onboarding_email")  # update path
    def test_create_staff_user_skips_last_login_update(self, mock_email):
        user = User.objects.create(username="staff", is_staff=True)
        post_save.send(
            sender=User,
            instance=user,
            created=False,
            update_fields={"last_login"},
        )
        mock_email.delay.assert_not_called()

    @patch("food_orders.signals.send_new_user_onboarding_email")  # update path
    def test_create_staff_user_triggers_onboarding(self, mock_email):
        user = User.objects.create(username="staff2", is_staff=True)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        mock_email.delay.assert_called_once_with(user_id=user.id)

    @patch("food_orders.signals.send_new_user_onboarding_email")  # update path
    def test_create_non_staff_user_does_not_trigger_onboarding(self, mock_email):
        User.objects.create(username="normal", is_staff=False)
        mock_email.delay.assert_not_called()


# ==========================
# Email Task Tests
# ==========================

class EmailTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="resetuser",
            email="reset@example.com",
            password="password123",
        )

    @patch("food_orders.tasks.send_email")  # update path
    def test_send_password_reset_email_calls_send_email(self, mock_send_email):
        send_password_reset_email(self.user.id)
        mock_send_email.assert_called_once_with(
            user=self.user,
            subject="Set Your Password",
            html_template="registration/password_reset_email.html",
            text_template="registration/password_reset_email.txt",
            email_type="password_reset",
            reply_to="it@loveyourneighbor.org",
        )

    def test_password_reset_email_creates_log_and_prevents_duplicates(self):
        send_password_reset_email(self.user.id)
        self.assertTrue(
            EmailLog.objects.filter(user=self.user, email_type="password_reset").exists()
        )
        with patch("food_orders.tasks.send_email") as mock_send_email:  # update path
            send_password_reset_email(self.user.id)
            mock_send_email.assert_not_called()

    def test_password_reset_email_handles_missing_user(self):
        with patch("food_orders.tasks.send_email") as mock_send_email:  # update path
            send_password_reset_email(999999)
            mock_send_email.assert_not_called()

    @patch("food_orders.tasks.send_email")  # update path
    def test_send_new_user_onboarding_email_calls_send_email(self, mock_send_email):
        send_new_user_onboarding_email(self.user.id)
        mock_send_email.assert_called_once_with(
            user=self.user,
            subject="Welcome to Love Your Neighbor!",
            html_template="registration/new_user_onboarding.html",
            text_template="registration/new_user_onboarding.txt",
            email_type="onboarding",
            reply_to="support@loveyourneighbor.org",
        )

    def test_onboarding_email_creates_log_and_prevents_duplicates(self):
        send_new_user_onboarding_email(self.user.id)
        self.assertTrue(
            EmailLog.objects.filter(user=self.user, email_type="onboarding").exists()
        )
        with patch("food_orders.tasks.send_email") as mock_send_email:  # update path
            send_new_user_onboarding_email(self.user.id)
            mock_send_email.assert_not_called()

    def test_onboarding_email_handles_missing_user(self):
        with patch("food_orders.tasks.send_email") as mock_send_email:  # update path
            send_new_user_onboarding_email(999999)
            mock_send_email.assert_not_called()
