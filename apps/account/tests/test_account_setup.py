# tests/test_signals_and_tasks_pytest.py

"""
================================================================================
Pytest Tests for Signals and Asynchronous Tasks
================================================================================

This file contains tests for the application's signals (e.g., creating a user
profile when a Participant is created) and Celery tasks (e.g., sending emails).

Key Pytest Concepts Used:
-------------------------
- **Fixtures (`@pytest.fixture`)**: Used to provide a consistent baseline state for
  tests, such as creating a default User or VoucherSetting.

- **`mocker` Fixture**: Provided by the `pytest-mock` plugin, this fixture is an
  easy way to patch objects and functions to isolate code and test specific
  behaviors without triggering side effects (like actual email sending).

- **Parametrization (`@pytest.mark.parametrize`)**: A powerful feature that
  allows running a single test function with multiple different sets of inputs.
  This is used to reduce code duplication when testing similar scenarios.
"""

# ============================================================
# Imports
# ============================================================

# --- Standard Library Imports ---
from decimal import Decimal
import logging
# --- Third-Party Imports ---
import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import override_settings

# --- Local Application Imports ---
# --- Models needed for testing ---
from apps.account.models import (
    AccountBalance,
    Participant,
    UserProfile,
)
from apps.voucher.models import (
    Voucher,
    VoucherSetting,
)
from apps.log.models import EmailLog
# --- Factories for creating model instances ---
from apps.pantry.tests.factories import ParticipantFactory

# --- The signals and tasks we intend to test ---
from apps.account.signals import initialize_participant
from apps.pantry.signals import create_staff_user_profile_and_onboarding
from apps.account.tasks.email import (
    send_new_user_onboarding_email,
    send_password_reset_email
)

logger = logging.getLogger(__name__)

# --- Get the User model configured in the Django project ---
User = get_user_model()


# ============================================================
# Test Fixtures
# ============================================================

@pytest.fixture
def voucher_setting_fixture():
    """Create a test voucher setting."""
    # Ensure no other active settings exist
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('50.00'),
        child_amount=Decimal('25.00'),
        infant_modifier=Decimal('10.00'),
        active=True
    )


@pytest.fixture
def test_user_fixture():
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='testpass123'
    )


@pytest.fixture
def email_type_onboarding():
    """Create or get onboarding email type for testing."""
    from apps.log.models import EmailType
    email_type, _ = EmailType.objects.get_or_create(
        name='onboarding',
        defaults={
            'subject': 'Welcome to {{ site_name }}',
            'html_template': '<p>Welcome {{ user.username }}!</p>',
            'text_template': 'Welcome {{ user.username }}!',
            'is_active': True
        }
    )
    # Ensure it's active even if it already existed
    if not email_type.is_active:
        email_type.is_active = True
        email_type.save()
    return email_type


@pytest.fixture
def email_settings():
    """Ensure email settings exist."""
    from core.models import EmailSettings
    settings, _ = EmailSettings.objects.get_or_create(
        pk=1,
        defaults={
            'from_email_default': 'noreply@example.com',
            'reply_to_default': 'support@example.com'
        }
    )
    return settings


# ============================================================
# Participant and Account Signal Tests
# ============================================================

# --- All tests in this section need database access ---
@pytest.mark.django_db
class TestParticipantCreationSignals:
    """
    A class to group related tests for signals that fire when a Participant
    model is created or updated. Using a class is optional in pytest but can
    help organize tests.
    """

    def test_account_and_vouchers_created_on_participant_create(self, voucher_setting_fixture):
        """
        Tests that creating a new Participant automatically triggers the creation
        of a related AccountBalance and the initial set of Vouchers.
        """
        # --- ARRANGE & ACT ---
        # --- Using the factory is cleaner than the old helper method. ---
        # --- The `voucher_setting_fixture` is passed to ensure settings exist. ---
        participant = ParticipantFactory()

        # --- ASSERT ---
        # --- `hasattr` checks if the `accountbalance` reverse relationship exists ---
        assert hasattr(participant, "accountbalance")

        # --- Check that the correct number of grocery vouchers were created by the signal ---
        voucher_count = Voucher.objects.filter(
            account__participant=participant, voucher_type="grocery"
        ).count()
        assert voucher_count == 2

    def test_no_duplicate_account_created_on_update(self, voucher_setting_fixture):
        """
        Ensures that simply updating a Participant's data does not trigger the
        creation of a new, duplicate AccountBalance or more vouchers.
        """
        # --- ARRANGE ---
        # --- Create the initial participant ---
        participant = ParticipantFactory()

        # --- ACT ---
        # --- Update a field and save the participant instance ---
        participant.name = "Updated Name"
        participant.save()

        # --- ASSERT ---
        # --- Verify that there is still only one AccountBalance for this participant ---
        assert AccountBalance.objects.filter(participant=participant).count() == 1
        # --- Verify the number of vouchers has not changed ---
        assert Voucher.objects.filter(account__participant=participant).count() == 2

    # --- Use `pytest.mark.parametrize` to run this test multiple times with different inputs ---
    # --- This avoids writing three separate, nearly identical test functions. ---
    @pytest.mark.parametrize(
        "field_to_change, new_value",
        [
            ("adults", 3),
            ("children", 2),
            ("diaper_count", 4),
        ],
    )
    def test_base_balance_updated_on_household_change(self, voucher_setting_fixture, field_to_change, new_value):
        """
        Tests that the account's base balance is correctly recalculated and increased
        whenever the number of adults, children, or infants changes.
        """
        # --- ARRANGE ---
        participant = ParticipantFactory()
        account_balance = participant.accountbalance
        initial_balance = account_balance.base_balance

        # --- ACT ---
        # --- `setattr` dynamically sets the attribute based on the parametrized field name ---
        setattr(participant, field_to_change, new_value)
        participant.save()  # This save triggers the signal that updates the balance.

        # --- Refresh the account balance object from the database to get the new value ---
        account_balance.refresh_from_db()

        # --- ASSERT ---
        # --- Ensure the balance has increased from its initial value ---
        assert account_balance.base_balance > initial_balance


# ============================================================
# User Creation and Onboarding Signal Tests
# ============================================================

@pytest.mark.django_db
class TestUserOnboardingSignals:
    """
    Tests for signals related to creating Users, UserProfiles, and triggering
    onboarding emails.
    """

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        CELERY_BROKER_BACKEND='memory',
        CELERY_RESULT_BACKEND='cache',
        CELERY_CACHE_BACKEND='memory'
    )
    def test_initialize_participant_creates_user_and_profile(
        self, voucher_setting_fixture, mocker
    ):
        """
        Tests that if `create_user=True`, the signal correctly calls the user
        creation utility, links the new user, and creates a UserProfile.
        """
        # --- ARRANGE ---
        # --- Patch the email task to prevent Celery connection attempts ---
        mocker.patch(
            "apps.account.signals.send_new_user_onboarding_email.delay"
        )
        # --- Use the `mocker` fixture to patch the user creation function ---
        # --- This isolates the test to the signal logic itself. ---
        mock_create_user = mocker.patch(
            "apps.account.signals.create_participant_user"
        )
        # Create a real user in the database instead of mock
        mock_user = User.objects.create(
            username="mocked",
            email="mocked@example.com"
        )
        # Make the patch return our real user
        mock_create_user.return_value = mock_user

        # --- ACT ---
        # --- Create a participant with the flag to create a user ---
        # Build the participant without saving
        participant = ParticipantFactory.build()
        # Set the create_user flag
        participant.create_user = True
        # Save to trigger the signal with create_user=True
        participant.save()
        participant.refresh_from_db()

        # --- ASSERT ---
        # --- Check that participant is linked to user ---
        assert participant.user == mock_user
        # --- Check that a UserProfile was created for this user ---
        assert UserProfile.objects.filter(user=mock_user).exists()

    def test_initialize_participant_triggers_onboarding_email(
        self, voucher_setting_fixture, mocker
    ):
        """
        Tests that creating a participant with a new user also triggers the
        onboarding email task.
        """
        # --- ARRANGE ---
        # --- Patch both the user creation and email sending functions ---
        mock_create_user = mocker.patch(
            "apps.account.signals.create_participant_user"
        )
        mock_send_email = mocker.patch(
            "apps.account.signals.send_new_user_onboarding_email.delay"
        )
        # Create a real user in the database instead of mock
        mock_user = User.objects.create(
            username="mocked2",
            email="mocked2@example.com"
        )
        mock_create_user.return_value = mock_user

        # --- ACT ---
        # Build the participant without saving
        participant = ParticipantFactory.build()
        # Set the create_user flag
        participant.create_user = True
        # Save to trigger the signal with create_user=True
        participant.save()

        # --- ASSERT ---
        # --- Verify that the email task's `.delay()` method was called ---
        mock_send_email.assert_called_once_with(user_id=mock_user.id)

    def test_create_staff_user_triggers_onboarding(self, mocker):
        """
        Tests that creating a new staff user directly (not via a Participant)
        triggers the staff onboarding signal and email task.
        """
        # --- ARRANGE ---
        # --- Patch the email task ---
        mock_email_task = mocker.patch(
            "apps.pantry.signals.send_new_user_onboarding_email.delay"
        )
        
        # --- ACT ---
        # --- Create a new staff user. The `post_save` signal will fire automatically. ---
        user = User.objects.create(username="staff_user", is_staff=True)

        # --- ASSERT ---
        # --- Check that a UserProfile was created for the new staff user ---
        assert UserProfile.objects.filter(user=user).exists()
        # --- Check that the onboarding email task was called ---
        mock_email_task.assert_called_once_with(user_id=user.id)
        

# ============================================================
# Email Task Tests
# ============================================================
@pytest.mark.django_db
class TestEmailTasks:
    """
    Tests for the Celery tasks that send emails. These tests do not actually
    send emails; they patch the sending mechanism to verify the tasks behave
    correctly.
    """

    def test_send_password_reset_email_logic(self, test_user_fixture, mocker):
        """
        Tests that the password reset task calls the underlying email utility
        with the correct arguments.
        """
        # --- ARRANGE ---
        user = test_user_fixture
        mock_send_email = mocker.patch(
            "apps.account.tasks.email.send_email_by_type"
        )

        # --- ACT ---
        # --- Call the task directly with the user's ID ---
        send_password_reset_email(user.id)

        # --- ASSERT ---
        # --- Verify `send_email_by_type` was called with the expected args ---
        mock_send_email.assert_called_once_with(
            user.id,
            "password_reset",
            force=False
        )

    def test_email_tasks_create_log_and_prevent_duplicates(
        self, test_user_fixture, email_type_onboarding, email_settings, mocker
    ):
        """
        Tests that sending an email creates an EmailLog, and a second attempt
        to send the same email type to the same user is blocked.
        """
        # --- ARRANGE ---
        user = test_user_fixture
        
        # Mock the database lookups to return our fixture objects
        # This avoids transaction visibility issues between test and task in CI
        mocker.patch(
            "apps.account.tasks.email.get_email_type",
            return_value=email_type_onboarding
        )
        mocker.patch(
            "apps.account.tasks.email.get_email_settings",
            return_value=email_settings
        )
        
        # Clean up any existing email logs for this user to ensure clean test state
        EmailLog.objects.filter(user=user).delete()
        
        mock_send_message = mocker.patch(
            "apps.account.tasks.email.send_email_message"
        )   
        
        # --- ACT (First Call) ---
        result = send_new_user_onboarding_email(user.id)
        
        # Debug: Check what the task returned
        logger.debug(f"Task returned: {result}")
        logger.debug(f"Mock call count: {mock_send_message.call_count}")

        # --- ASSERT (First Call) ---
        # --- Check that the email was sent the first time ---
        assert mock_send_message.call_count == 1, \
            f"Expected 1 call but got {mock_send_message.call_count}. Task result: {result}"
        # --- Check that a log was created in the database ---
        assert EmailLog.objects.filter(user=user, email_type__name="onboarding").exists()

        # --- Debugging: Print EmailLog entries after the first call
        logger.debug(EmailLog.objects.all())

        # --- ACT (Second Call) ---
        # --- Call the task again ---
        send_new_user_onboarding_email(user.id)

        # --- ASSERT (Second Call) ---
        # --- The call count should NOT have increased, proving the duplicate was blocked ---
        assert mock_send_message.call_count == 1, "Email should not be sent a second time"

    def test_email_tasks_handle_missing_user_gracefully(self, mocker):
        """
        Tests that if a task is called with an ID for a user that no longer
        exists, it does not crash - send_email_by_type handles it gracefully.
        """
        # --- ARRANGE ---
        non_existent_user_id = 999999

        # --- ACT & ASSERT ---
        # --- Call both tasks with an ID that doesn't exist - should not crash ---
        result1 = send_password_reset_email(non_existent_user_id)
        result2 = send_new_user_onboarding_email(non_existent_user_id)
        
        # --- Both should return False since user doesn't exist ---
        assert result1 is False
        assert result2 is False


# ============================================================
# Admin Action Tests
# ============================================================


@pytest.mark.django_db
class TestParticipantAdminActions:
    """Test admin actions for Participant model."""

    def test_reset_password_and_send_email_action(self, mocker):
        """
        Test that the reset_password_and_send_email admin action:
        1. Resets the user's password
        2. Sets must_change_password flag
        3. Sends password reset email
        """
        from apps.account.admin import ParticipantAdmin
        from apps.orders.tests.factories import (
            UserFactory,
            ProgramFactory
        )
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        # Mock the Celery task
        mock_send_email_task = mocker.patch(
            "apps.account.admin.send_password_reset_email.delay"
        )
        
        # Mock the signal to prevent it from creating AccountBalance
        mocker.patch("apps.account.signals.setup_account_and_vouchers")

        # Create test data manually to avoid factory conflicts
        user1 = UserFactory(email="user1@test.com")
        user2 = UserFactory(email="user2@test.com")
        program = ProgramFactory()
        
        participant1 = Participant.objects.create(
            name="Test Participant 1",
            email="participant1@test.com",
            user=user1,
            program=program
        )
        participant2 = Participant.objects.create(
            name="Test Participant 2",
            email="participant2@test.com",
            user=user2,
            program=program
        )
        
        # Create AccountBalance records manually
        # Use get_or_create in case signal already created them
        AccountBalance.objects.get_or_create(
            participant=participant1,
            defaults={'base_balance': Decimal("100.00")}
        )
        AccountBalance.objects.get_or_create(
            participant=participant2,
            defaults={'base_balance': Decimal("100.00")}
        )
        
        # Get original password hashes
        original_hash1 = user1.password
        original_hash2 = user2.password

        # Setup admin
        site = AdminSite()
        admin = ParticipantAdmin(Participant, site)
        
        # Mock message_user to avoid middleware requirement
        admin.message_user = mocker.Mock()
        
        request = RequestFactory().get('/')        # Create queryset
        queryset = Participant.objects.filter(
            id__in=[participant1.id, participant2.id]
        )
        
        # Execute action
        admin.reset_password_and_send_email(request, queryset)
        
        # Refresh users from database
        user1.refresh_from_db()
        user2.refresh_from_db()
        
        # Verify passwords were changed
        assert user1.password != original_hash1
        assert user2.password != original_hash2
        
        # Verify must_change_password flag is set
        profile1 = UserProfile.objects.get(user=user1)
        profile2 = UserProfile.objects.get(user=user2)
        assert profile1.must_change_password is True
        assert profile2.must_change_password is True
        
        # Verify email task was called for both users
        assert mock_send_email_task.call_count == 2
        mock_send_email_task.assert_any_call(user1.id)
        mock_send_email_task.assert_any_call(user2.id)

    def test_reset_password_skips_participants_without_user(self, mocker):
        """
        Test that participants without a user are skipped gracefully.
        """
        from apps.account.admin import ParticipantAdmin
        from apps.orders.tests.factories import ProgramFactory
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        # Mock the Celery task
        mock_send_email_task = mocker.patch(
            "apps.account.admin.send_password_reset_email.delay"
        )
        
        # Mock the signal to prevent it from creating AccountBalance
        mocker.patch("apps.account.signals.setup_account_and_vouchers")

        # Create participant manually without user
        program = ProgramFactory()
        participant = Participant.objects.create(
            name="No User Participant",
            email="nouser@test.com",
            user=None,
            program=program
        )
        
        # Create AccountBalance manually
        # Use get_or_create in case signal already created it
        AccountBalance.objects.get_or_create(
            participant=participant,
            defaults={'base_balance': Decimal("100.00")}
        )
        
        # Setup admin
        site = AdminSite()
        admin = ParticipantAdmin(Participant, site)
        
        # Mock message_user to avoid middleware requirement
        admin.message_user = mocker.Mock()
        
        request = RequestFactory().get('/')
        
        # Create queryset
        queryset = Participant.objects.filter(id=participant.id)
        
        # Execute action - should not crash
        admin.reset_password_and_send_email(request, queryset)
        
        # Verify email task was not called
        mock_send_email_task.assert_not_called()
