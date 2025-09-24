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

# --- Third-Party Imports ---
import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

# --- Local Application Imports ---
# --- Models needed for testing ---
from food_orders.models import (
    AccountBalance,
    Voucher,
    Participant,
    VoucherSetting,
    UserProfile,
    EmailLog,
)
# --- Factories for creating model instances ---
from factories import ParticipantFactory

# --- The signals and tasks we intend to test ---
from food_orders.signals import initialize_participant, create_staff_user_profile_and_onboarding
from food_orders.tasks import send_new_user_onboarding_email, send_password_reset_email

# --- Get the User model configured in the Django project ---
User = get_user_model()


# ============================================================
# Pytest Fixtures
# ============================================================
"""
These fixtures set up common objects needed across multiple tests. By defining
them here, we avoid repeating the same setup code in every test function.
For a larger project, these would typically be placed in a `conftest.py` file
to be automatically available to all test files.
"""

@pytest.fixture
def voucher_setting_fixture():
    """
    Creates a default, active `VoucherSetting` object in the database.
    This is required for tests involving participant creation, as signals
    rely on these settings to calculate initial balances.
    """
    # --- Create the setting and return it ---
    return VoucherSetting.objects.create(
        adult_amount=10,
        child_amount=5,
        infant_modifier=2,
        active=True,
    )

@pytest.fixture
def test_user_fixture():
    """
    Creates a standard Django User for use in email task tests.
    """
    # --- Use Django's `create_user` helper for a standard user ---
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="password123",
    )


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
        participant.save() # This save triggers the signal that updates the balance.

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

    def test_initialize_participant_creates_user_and_profile(self, voucher_setting_fixture, mocker):
        """
        Tests that if `create_user=True`, the signal correctly calls the user
        creation utility, links the new user, and creates a UserProfile.
        """
        # --- ARRANGE ---
        # --- Use the `mocker` fixture to patch the user creation function ---
        # --- This isolates the test to the signal logic itself. ---
        mock_create_user = mocker.patch("food_orders.signals.create_participant_user")
        mock_user = User(id=1, username="mocked") # A mock User object
        mock_create_user.return_value = mock_user # Make the patch return our mock user

        # --- ACT ---
        # --- Create a participant with the flag to create a user ---
        participant = ParticipantFactory(create_user=True)
        participant.refresh_from_db()

        # --- ASSERT ---
        # --- Check that the participant is now linked to the user returned by the mock ---
        assert participant.user == mock_user
        # --- Check that a UserProfile was created for this user ---
        assert UserProfile.objects.filter(user=mock_user).exists()

    def test_initialize_participant_triggers_onboarding_email(self, voucher_setting_fixture, mocker):
        """
        Tests that creating a participant with a new user also triggers the
        onboarding email task.
        """
        # --- ARRANGE ---
        # --- Patch both the user creation and email sending functions ---
        mock_create_user = mocker.patch("food_orders.signals.create_participant_user")
        mock_send_email = mocker.patch("food_orders.signals.send_new_user_onboarding_email.delay")
        mock_user = User(id=2, username="mocked2")
        mock_create_user.return_value = mock_user

        # --- ACT ---
        ParticipantFactory(create_user=True)

        # --- ASSERT ---
        # --- Verify that the email task's `.delay()` method was called exactly once with the new user's ID ---
        mock_send_email.assert_called_once_with(user_id=mock_user.id)

    def test_create_staff_user_triggers_onboarding(self, mocker):
        """
        Tests that creating a new staff user directly (not via a Participant)
        triggers the staff onboarding signal and email task.
        """
        # --- ARRANGE ---
        # --- Patch the email task ---
        mock_email_task = mocker.patch("food_orders.signals.send_new_user_onboarding_email.delay")
        
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
        mock_send_email = mocker.patch("food_orders.tasks.send_email")

        # --- ACT ---
        # --- Call the task directly with the user's ID ---
        send_password_reset_email(user.id)

        # --- ASSERT ---
        # --- Verify `send_email` was called with the expected context ---
        mock_send_email.assert_called_once_with(
            user=user,
            subject="Set Your Password",
            html_template="registration/password_reset_email.html",
            text_template="registration/password_reset_email.txt",
            email_type="password_reset",
            reply_to="it@loveyourneighbor.org",
        )

    def test_email_tasks_create_log_and_prevent_duplicates(self, test_user_fixture, mocker):
        """
        Tests that sending an email creates an EmailLog, and a second attempt
        to send the same email type to the same user is blocked.
        """
        # --- ARRANGE ---
        user = test_user_fixture
        mock_send_email = mocker.patch("food_orders.tasks.send_email")
        
        # --- ACT (First Call) ---
        send_new_user_onboarding_email(user.id)

        # --- ASSERT (First Call) ---
        # --- Check that the email was sent the first time ---
        assert mock_send_email.call_count == 1
        # --- Check that a log was created in the database ---
        assert EmailLog.objects.filter(user=user, email_type="onboarding").exists()

        # --- ACT (Second Call) ---
        # --- Call the task again ---
        send_new_user_onboarding_email(user.id)
        
        # --- ASSERT (Second Call) ---
        # --- The call count should NOT have increased, proving the duplicate was blocked ---
        assert mock_send_email.call_count == 1, "Email should not be sent a second time"

    def test_email_tasks_handle_missing_user_gracefully(self, mocker):
        """
        Tests that if a task is called with an ID for a user that no longer
        exists, it does not crash and does not attempt to send an email.
        """
        # --- ARRANGE ---
        mock_send_email = mocker.patch("food_orders.tasks.send_email")
        non_existent_user_id = 999999

        # --- ACT ---
        # --- Call both tasks with an ID that doesn't exist in the database ---
        send_password_reset_email(non_existent_user_id)
        send_new_user_onboarding_email(non_existent_user_id)

        # --- ASSERT ---
        # --- Verify that the email sending function was never called ---
        mock_send_email.assert_not_called()