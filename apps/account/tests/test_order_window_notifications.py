"""
Tests for apps.account.tasks.order_window — order-window email notifications.

Business rules verified:
  1. Emails fire when a window just opened (within the 10-min lookback).
  2. No emails fire when a program pause is currently active.
  3. No emails fire when the order window is disabled globally.
  4. No emails fire when the window has not opened yet.
  5. No emails fire when the window already closed (opened > 10 min ago).
  6. Per-cycle deduplication: a participant who was already notified this
     cycle is not emailed again.
  7. Participants without a linked User are skipped.
  8. Inactive participants are skipped.
  9. The double-order week (pre-pause) still triggers notifications because
     the pause itself hasn't started yet.
 10. Multiple participants each receive exactly one email.
 11. Archived pauses are ignored; window fires normally.
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.utils import timezone
from freezegun import freeze_time

from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program, ProgramPause
from apps.log.models import EmailLog, EmailType
from apps.voucher.models import Voucher, VoucherSetting
from core.models import OrderWindowSettings
from core.utils import generate_window_cycles, get_effective_config

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _required_singletons(db):
    """Ensure global singletons exist for every test."""
    OrderWindowSettings.get_settings()
    VoucherSetting.objects.get_or_create(
        active=True,
        defaults=dict(
            adult_amount=Decimal("50.00"),
            child_amount=Decimal("25.00"),
            infant_modifier=Decimal("10.00"),
        ),
    )


@pytest.fixture
def email_type(db):
    """Active `order_window_opened` EmailType."""
    et, _ = EmailType.objects.get_or_create(
        name="order_window_opened",
        defaults=dict(
            display_name="Order Window Opened",
            subject="Your order window is open",
            html_content="<p>Hi {{ participant_name }}, window is open.</p>",
            text_content="Hi {{ participant_name }}, window is open.",
            is_active=True,
        ),
    )
    if not et.is_active:
        et.is_active = True
        et.save()
    return et


@pytest.fixture
def monday_program(db):
    """A Monday 09:00 (America/New_York) program with 24 h window."""
    return Program.objects.create(
        name="Monday Morning",
        MeetingDay="monday",
        meeting_time="09:00:00",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_participant_with_user(program, *, name="Alice", suffix="1"):
    """Create a Participant + linked User without triggering onboarding signals."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_user(
        username=f"testuser_{suffix}",
        email=f"testuser_{suffix}@example.com",
        password="pass",
    )
    p = Participant(
        name=name,
        email=f"testuser_{suffix}@example.com",
        program=program,
        active=True,
        user=user,
        adults=1,
    )
    p._skip_onboarding_signal = True
    p.save()
    AccountBalance.objects.get_or_create(
        participant=p,
        defaults={"base_balance": Decimal("50.00")},
    )
    return p


def _get_next_window_opens_at(program):
    """
    Return the opens_at for the immediately next window cycle.
    Uses the real system time so the result is in the server's local timezone,
    consistent with what generate_window_cycles produces inside the task.
    """
    config = get_effective_config(program)
    cycles = generate_window_cycles(program, config, n=2)
    assert cycles, "Program must have at least one valid window cycle"
    return cycles[0]["opens_at"], cycles[0]["closes_at"]


def _run_task_frozen_at(frozen_now):
    """
    Run notify_participants_order_window_opened() with time frozen to
    `frozen_now` and the actual email dispatch patched out.
    Returns the MagicMock so tests can assert on call counts / args.
    """
    from apps.account.tasks.order_window import notify_participants_order_window_opened

    mock_send = MagicMock()
    patch_target = "apps.account.tasks.email.send_order_window_opened_notification.delay"
    with freeze_time(frozen_now), patch(patch_target, mock_send):
        notify_participants_order_window_opened()

    return mock_send


# ---------------------------------------------------------------------------
# 1. Happy path — window just opened, participant is notified
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_email_sent_when_window_just_opened(monday_program, email_type):
    """Participants receive a notification when their window opens."""
    participant = _make_participant_with_user(monday_program)

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    mock_send = _run_task_frozen_at(frozen_now)

    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["user_id"] == participant.user.id
    assert "Monday Morning" in call_kwargs["program_name"]


# ---------------------------------------------------------------------------
# 2. Active program pause — NO emails
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_email_during_active_program_pause(monday_program, email_type):
    """Pause active right now → task exits before touching any program."""
    _make_participant_with_user(monday_program)

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    # Pause spans frozen_now
    ProgramPause.objects.create(
        pause_start=frozen_now - timedelta(hours=1),
        pause_end=frozen_now + timedelta(days=7),
        reason="Memorial Day",
    )

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Order window globally disabled — NO emails
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_email_when_order_window_disabled(monday_program, email_type):
    """Global order window disabled → no notifications."""
    _make_participant_with_user(monday_program)

    settings = OrderWindowSettings.get_settings()
    settings.enabled = False
    settings.save()

    try:
        opens_at, _ = _get_next_window_opens_at(monday_program)
        frozen_now = opens_at + timedelta(minutes=1)
        mock_send = _run_task_frozen_at(frozen_now)
        mock_send.assert_not_called()
    finally:
        settings.enabled = True
        settings.save()


# ---------------------------------------------------------------------------
# 4. Window not yet open — NO emails
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_email_before_window_opens(monday_program, email_type):
    """When the window hasn't opened yet, no email is dispatched."""
    _make_participant_with_user(monday_program)

    opens_at, _ = _get_next_window_opens_at(monday_program)
    # 30 minutes BEFORE the window opens
    frozen_now = opens_at - timedelta(minutes=30)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 5. Window opened more than 10 minutes ago — NOT a new open event
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_email_when_window_opened_long_ago(monday_program, email_type):
    """Window opened >10 min ago — not a 'just opened' event, no email."""
    _make_participant_with_user(monday_program)

    opens_at, _ = _get_next_window_opens_at(monday_program)
    # 2 hours AFTER the window opened (well outside the 10-min lookback)
    frozen_now = opens_at + timedelta(hours=2)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Per-cycle deduplication — already-notified participant skipped
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_no_duplicate_email_same_cycle(monday_program, email_type):
    """A participant already emailed for this cycle is not emailed again."""
    participant = _make_participant_with_user(monday_program)

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=2)

    # Pre-seed the EmailLog as if sent 30s after the window opened
    with freeze_time(opens_at + timedelta(seconds=30)):
        EmailLog.objects.create(
            user=participant.user,
            email_type=email_type,
            subject="Your order window is open",
            status="sent",
        )

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 7. Participant without a linked User is skipped
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_participant_without_user_is_skipped(monday_program, email_type):
    """Participants with no linked User account never receive emails."""
    p = Participant(
        name="No User",
        email="nouser@example.com",
        program=monday_program,
        active=True,
        adults=1,
    )
    p._skip_onboarding_signal = True
    p.save()
    # Detach the auto-created user to simulate legacy/manually-cleared data.
    p.user = None
    p.save(update_fields=["user"])
    AccountBalance.objects.get_or_create(
        participant=p,
        defaults={"base_balance": Decimal("50.00")},
    )

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Inactive participant is skipped
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_inactive_participant_is_skipped(monday_program, email_type):
    """Inactive participants are excluded from notifications."""
    participant = _make_participant_with_user(monday_program, suffix="inactive")
    participant.active = False
    participant.save(update_fields=["active"])

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 9. Pre-pause "double order" week — pause is scheduled but not yet active
#    → emails SHOULD fire normally
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_email_sent_during_pre_pause_double_order_week(monday_program, email_type):
    """
    The week BEFORE a pause (double-order week) is a normal order week.
    A ProgramPause exists but pause_start is in the future —
    the pause is not active so notifications must still fire.
    """
    _make_participant_with_user(monday_program, suffix="double")

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    # Pause starts next week — NOT active at frozen_now
    ProgramPause.objects.create(
        pause_start=frozen_now + timedelta(days=7),
        pause_end=frozen_now + timedelta(days=14),
        reason="Memorial Day",
    )

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# 10. Multiple participants — each receives exactly one email
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_all_active_participants_notified(monday_program, email_type):
    """Every active participant with a User gets exactly one notification."""
    p1 = _make_participant_with_user(monday_program, name="Alice", suffix="multi1")
    p2 = _make_participant_with_user(monday_program, name="Bob", suffix="multi2")

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    mock_send = _run_task_frozen_at(frozen_now)

    assert mock_send.call_count == 2
    notified_user_ids = {c.kwargs["user_id"] for c in mock_send.call_args_list}
    assert notified_user_ids == {p1.user.id, p2.user.id}


# ---------------------------------------------------------------------------
# 11. Archived pause is ignored — emails still fire
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_archived_pause_does_not_block_emails(monday_program, email_type):
    """An archived pause record is ignored; the window opens normally."""
    _make_participant_with_user(monday_program, suffix="arc")

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    # Archived pause that would otherwise span frozen_now
    ProgramPause.objects.create(
        pause_start=frozen_now - timedelta(hours=1),
        pause_end=frozen_now + timedelta(days=7),
        reason="Archived — should be ignored",
        archived=True,
    )

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# 12. Beat 25 minutes late — wider lookback still catches the window
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_email_fires_when_beat_runs_25_minutes_late(monday_program, email_type):
    """
    Old 10-min lookback would miss a beat 25 min late.
    The widened 30-min lookback must still fire the notification.
    """
    _make_participant_with_user(monday_program, suffix="late")

    opens_at, _ = _get_next_window_opens_at(monday_program)
    # 25 min after window opened — outside old 10-min window, inside new 30-min window
    frozen_now = opens_at + timedelta(minutes=25)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# 13. Integration — full pipeline writes an EmailLog row
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_email_log_created_on_full_pipeline(monday_program, email_type):
    """
    Full call stack (no mocks): send_order_window_opened_notification must
    write an EmailLog row with status='sent'.

    This is the regression guard for the force=True fix — if force is ever
    removed from the send_email_by_type call inside the wrapper task, this
    test will fail on the second run (a prior EmailLog row exists and the
    lifetime has_email_been_sent gate would silently drop the email).
    """
    from django.test.utils import override_settings as _override
    from apps.account.tasks.email import send_order_window_opened_notification
    from core.models import EmailSettings

    EmailSettings.get_settings()  # ensure singleton exists

    participant = _make_participant_with_user(monday_program, suffix="integration")

    with _override(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
        result = send_order_window_opened_notification(
            user_id=participant.user.id,
            program_name=monday_program.name,
            closes_at_str="Monday, June 3 at 9:00 AM",
        )

    assert result is True
    assert EmailLog.objects.filter(
        user=participant.user,
        email_type__name="order_window_opened",
        status="sent",
    ).exists()


# ---------------------------------------------------------------------------
# 14. Per-program enabled=False overrides global enabled=True
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_per_program_disabled_overrides_global_enabled(monday_program, email_type):
    """Per-program enabled=False must block notifications even when global is True."""
    from core.models import ProgramOrderWindow

    _make_participant_with_user(monday_program, suffix="pgm_disabled")
    opens_at, _ = _get_next_window_opens_at(monday_program)

    # Disable the window specifically for this program after computing opens_at.
    ProgramOrderWindow.objects.create(program=monday_program, enabled=False)

    frozen_now = opens_at + timedelta(minutes=1)
    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 15. Per-program enabled=True overrides global enabled=False
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_per_program_enabled_overrides_global_disabled(monday_program, email_type):
    """Per-program enabled=True must still send even when global is False."""
    from core.models import ProgramOrderWindow

    _make_participant_with_user(monday_program, suffix="pgm_enabled")
    opens_at, _ = _get_next_window_opens_at(monday_program)

    global_settings = OrderWindowSettings.get_settings()
    global_settings.enabled = False
    global_settings.save()

    ProgramOrderWindow.objects.create(program=monday_program, enabled=True)

    try:
        frozen_now = opens_at + timedelta(minutes=1)
        mock_send = _run_task_frozen_at(frozen_now)
        mock_send.assert_called_once()
    finally:
        global_settings.enabled = True
        global_settings.save()


# ---------------------------------------------------------------------------
# 16. Participant whose User has an empty email is skipped
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_empty_email_participant_skipped(monday_program, email_type):
    """Participants whose linked User has email='' must not be dispatched."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user = User.objects.create_user(
        username="noemail_user",
        email="",
        password="pass",
    )
    p = Participant(
        name="No Email",
        email="placeholder@example.com",
        program=monday_program,
        active=True,
        user=user,
        adults=1,
    )
    p._skip_onboarding_signal = True
    p.save()
    AccountBalance.objects.get_or_create(
        participant=p,
        defaults={"base_balance": Decimal("50.00")},
    )

    opens_at, _ = _get_next_window_opens_at(monday_program)
    frozen_now = opens_at + timedelta(minutes=1)

    mock_send = _run_task_frozen_at(frozen_now)
    mock_send.assert_not_called()

