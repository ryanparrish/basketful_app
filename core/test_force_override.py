"""
Regression tests for ProgramWindowOverride (force-open / force-closed).

Issue #68: Staff reported that force-open and force-closed overrides had
no visible effect on the participant's order window.

Triage protocol — these tests characterise the current behaviour at every
layer of the stack:
  1. can_place_order() utility
  2. get_program_window_status() utility
  3. POST /api/v1/programs/{id}/order-window/override/  (staff creates override)
  4. DELETE /api/v1/programs/{id}/order-window/override/  (staff clears override)
  5. GET /api/v1/settings/my-window/  (participant checks their window)

If any test fails it pinpoints exactly which layer contains the bug.
"""
import pytest
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program
from core.models import OrderWindowSettings, ProgramWindowOverride
from core.utils import can_place_order, get_program_window_status, generate_window_cycles, get_effective_config

User = get_user_model()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def global_settings(db):
    """Ensure global order window singleton exists and is enabled."""
    s = OrderWindowSettings.get_settings()
    s.enabled = True
    s.hours_before_class = 24
    s.hours_before_close = 0
    s.save()
    return s


@pytest.fixture
def program(db):
    return Program.objects.create(
        name="Monday Program",
        MeetingDay="monday",
        meeting_time="09:00:00",
    )


@pytest.fixture
def participant(db, program):
    p = Participant(
        name="Test Participant",
        email="participant@example.com",
        program=program,
        active=True,
        adults=1,
    )
    p._skip_onboarding_signal = True
    p.save()
    AccountBalance.objects.get_or_create(
        participant=p, defaults={"base_balance": Decimal("50.00")}
    )
    return p


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff_tester", password="pass", is_staff=True
    )


@pytest.fixture
def participant_user(db):
    return User.objects.create_user(
        username="participant_user", password="pass", is_staff=False
    )


@pytest.fixture
def participant_with_user(db, program, participant_user):
    """Participant linked to a user account (for /my-window/ endpoint)."""
    p = Participant(
        name="Linked Participant",
        email="linked@example.com",
        program=program,
        active=True,
        adults=1,
        user=participant_user,
    )
    p._skip_onboarding_signal = True
    p.save()
    AccountBalance.objects.get_or_create(
        participant=p, defaults={"base_balance": Decimal("50.00")}
    )
    return p


@pytest.fixture
def staff_client(staff_user):
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


@pytest.fixture
def participant_client(participant_user):
    client = APIClient()
    client.force_authenticate(user=participant_user)
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_window_opens_at(program):
    """Return opens_at for the immediately next window cycle."""
    config = get_effective_config(program)
    cycles = generate_window_cycles(program, config, n=1)
    assert cycles, "Program must have at least one valid window cycle"
    return cycles[0]["opens_at"], cycles[0]["closes_at"]


# ---------------------------------------------------------------------------
# Layer 1: can_place_order() with force overrides
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_force_open_allows_ordering_outside_normal_window(program, participant):
    """
    Hypothesis: a non-expired force_open override makes can_place_order()
    return True even when the schedule-based window is closed.

    Prediction: can_order is True and context['force_override'] == 'open'.
    Falsification: if can_order is False, the override is being ignored.
    """
    opens_at, _closes_at = _next_window_opens_at(program)
    # frozen_now must be defined BEFORE the override so expires_at is
    # in the future relative to the frozen clock, not real time.
    frozen_now = opens_at - timedelta(hours=2)

    ProgramWindowOverride.objects.create(
        program=program,
        force_status="open",
        expires_at=frozen_now + timedelta(hours=6),
        reason="Inventory delay — keep window open",
    )

    # Freeze time to OUTSIDE the normal window (2 hours before it opens)
    with freeze_time(frozen_now):
        can_order, context = can_place_order(participant)

    assert can_order is True, (
        "force_open override should allow ordering even outside the scheduled window"
    )
    assert context.get("force_override") == "open"


@pytest.mark.django_db
def test_force_closed_blocks_ordering_inside_normal_window(program, participant):
    """
    Hypothesis: a non-expired force_closed override makes can_place_order()
    return False even when the schedule-based window is open.

    Prediction: can_order is False and context['force_override'] == 'closed'.
    Falsification: if can_order is True, the override is being ignored.
    """
    opens_at, _closes_at = _next_window_opens_at(program)

    ProgramWindowOverride.objects.create(
        program=program,
        force_status="closed",
        expires_at=opens_at + timedelta(hours=12),
        reason="Emergency stock audit",
    )

    # Freeze time to INSIDE the normal window (1 minute after opens_at)
    with freeze_time(opens_at + timedelta(minutes=1)):
        can_order, context = can_place_order(participant)

    assert can_order is False, (
        "force_closed override should block ordering even inside the scheduled window"
    )
    assert context.get("force_override") == "closed"


@pytest.mark.django_db
def test_expired_force_override_falls_back_to_schedule(program, participant):
    """
    An expired override must be lazily deleted and the schedule used instead.

    Prediction: context has no force_override key; the override row is gone.
    """
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="open",
        expires_at=timezone.now() - timedelta(minutes=1),
        reason="Already expired",
    )

    _can_order, context = can_place_order(participant)

    assert context.get("force_override") is None, (
        "Expired override should not be reflected in context"
    )
    # Lazy deletion: the expired row should have been removed
    assert not ProgramWindowOverride.objects.filter(program=program).exists(), (
        "can_place_order() should lazily delete expired override rows"
    )


# ---------------------------------------------------------------------------
# Layer 2: get_program_window_status() with force overrides
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_program_window_status_returns_force_open(program):
    """get_program_window_status() must return window_status='force_open'."""
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="open",
        expires_at=timezone.now() + timedelta(hours=4),
    )

    status = get_program_window_status(program)

    assert status["window_status"] == "force_open", (
        f"Expected 'force_open', got '{status['window_status']}'"
    )
    assert status["override"] is not None


@pytest.mark.django_db
def test_get_program_window_status_returns_force_closed(program):
    """get_program_window_status() must return window_status='force_closed'."""
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="closed",
        expires_at=timezone.now() + timedelta(hours=4),
    )

    status = get_program_window_status(program)

    assert status["window_status"] == "force_closed", (
        f"Expected 'force_closed', got '{status['window_status']}'"
    )
    assert status["override"] is not None


@pytest.mark.django_db
def test_get_program_window_status_seconds_until_change_reflects_expiry(program):
    """seconds_until_change should reflect how long until the override expires."""
    future = timezone.now() + timedelta(hours=2)
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="open",
        expires_at=future,
    )

    status = get_program_window_status(program)

    assert status["seconds_until_change"] is not None
    # Should be within a few seconds of 7200 (2 hours)
    assert abs(status["seconds_until_change"] - 7200) < 5


# ---------------------------------------------------------------------------
# Layer 3: POST /api/v1/programs/{id}/order-window/override/  (staff)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_staff_can_create_force_open_override(staff_client, program):
    """Staff POST to the override endpoint creates a force_open record."""
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    expires_at = (timezone.now() + timedelta(hours=4)).isoformat()

    response = staff_client.post(
        url,
        {"force_status": "open", "expires_at": expires_at, "reason": "Testing"},
        format="json",
    )

    assert response.status_code == 201, (
        f"Expected 201, got {response.status_code}: {response.data}"
    )
    assert ProgramWindowOverride.objects.filter(
        program=program, force_status="open"
    ).exists()


@pytest.mark.django_db
def test_staff_can_create_force_closed_override(staff_client, program):
    """Staff POST to the override endpoint creates a force_closed record."""
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    expires_at = (timezone.now() + timedelta(hours=4)).isoformat()

    response = staff_client.post(
        url,
        {"force_status": "closed", "expires_at": expires_at, "reason": "Audit"},
        format="json",
    )

    assert response.status_code == 201, (
        f"Expected 201, got {response.status_code}: {response.data}"
    )
    assert ProgramWindowOverride.objects.filter(
        program=program, force_status="closed"
    ).exists()


@pytest.mark.django_db
def test_non_staff_cannot_create_override(participant_client, program):
    """Non-staff users must receive 403 when trying to create an override."""
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    expires_at = (timezone.now() + timedelta(hours=4)).isoformat()

    response = participant_client.post(
        url,
        {"force_status": "open", "expires_at": expires_at},
        format="json",
    )

    assert response.status_code == 403, (
        f"Expected 403, got {response.status_code}"
    )
    assert not ProgramWindowOverride.objects.filter(program=program).exists()


@pytest.mark.django_db
def test_override_with_past_expiry_is_rejected(staff_client, program):
    """expires_at in the past must return 400."""
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    expires_at = (timezone.now() - timedelta(hours=1)).isoformat()

    response = staff_client.post(
        url,
        {"force_status": "open", "expires_at": expires_at},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_force_status_is_rejected(staff_client, program):
    """force_status values other than 'open'/'closed' must return 400."""
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    expires_at = (timezone.now() + timedelta(hours=4)).isoformat()

    response = staff_client.post(
        url,
        {"force_status": "maybe", "expires_at": expires_at},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_staff_can_delete_override(staff_client, program):
    """Staff DELETE clears an existing override."""
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="closed",
        expires_at=timezone.now() + timedelta(hours=4),
    )

    url = f"/api/v1/programs/{program.id}/order-window/override/"
    response = staff_client.delete(url)

    assert response.status_code == 204, (
        f"Expected 204, got {response.status_code}"
    )
    assert not ProgramWindowOverride.objects.filter(program=program).exists()


@pytest.mark.django_db
def test_second_override_replaces_first(staff_client, program):
    """
    POSTing a second override must upsert (update_or_create), not create a
    second row — the OneToOne constraint should be respected.
    """
    url = f"/api/v1/programs/{program.id}/order-window/override/"
    future = (timezone.now() + timedelta(hours=4)).isoformat()

    staff_client.post(url, {"force_status": "open", "expires_at": future}, format="json")
    staff_client.post(url, {"force_status": "closed", "expires_at": future}, format="json")

    overrides = ProgramWindowOverride.objects.filter(program=program)
    assert overrides.count() == 1, "Only one override row should exist per program"
    assert overrides.first().force_status == "closed"


# ---------------------------------------------------------------------------
# Layer 4: GET /api/v1/settings/my-window/ — participant view
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_my_window_returns_force_open_when_override_active(
    participant_client, participant_with_user, program
):
    """
    GET /settings/my-window/ must return is_open=True and
    window_status='force_open' when a non-expired force_open override exists,
    even if the schedule-based window is currently closed.
    """
    opens_at, _closes_at = _next_window_opens_at(program)
    # expires_at must be relative to frozen_now, not to real wall-clock time.
    frozen_now = opens_at - timedelta(hours=2)

    ProgramWindowOverride.objects.create(
        program=program,
        force_status="open",
        expires_at=frozen_now + timedelta(hours=4),
    )

    # Freeze to outside the normal window
    with freeze_time(frozen_now):
        response = participant_client.get("/api/v1/settings/my-window/")

    assert response.status_code == 200, response.data
    data = response.json()

    assert data["is_open"] is True, (
        f"Expected is_open=True with force_open override, got {data}"
    )
    assert data["window_status"] == "force_open", (
        f"Expected window_status='force_open', got '{data['window_status']}'"
    )


@pytest.mark.django_db
def test_my_window_returns_force_closed_when_override_active(
    participant_client, participant_with_user, program
):
    """
    GET /settings/my-window/ must return is_open=False and
    window_status='force_closed' when a non-expired force_closed override
    exists, even if the schedule-based window is currently open.
    """
    opens_at, _closes_at = _next_window_opens_at(program)

    ProgramWindowOverride.objects.create(
        program=program,
        force_status="closed",
        expires_at=opens_at + timedelta(hours=12),
    )

    # Freeze to inside the normal window
    with freeze_time(opens_at + timedelta(minutes=1)):
        response = participant_client.get("/api/v1/settings/my-window/")

    assert response.status_code == 200, response.data
    data = response.json()

    assert data["is_open"] is False, (
        f"Expected is_open=False with force_closed override, got {data}"
    )
    assert data["window_status"] == "force_closed", (
        f"Expected window_status='force_closed', got '{data['window_status']}'"
    )


@pytest.mark.django_db
def test_my_window_override_reason_is_returned(participant_client, participant_with_user, program):
    """override_reason must be surfaced to the participant."""
    ProgramWindowOverride.objects.create(
        program=program,
        force_status="closed",
        expires_at=timezone.now() + timedelta(hours=4),
        reason="Emergency stock audit — back shortly",
    )

    response = participant_client.get("/api/v1/settings/my-window/")

    assert response.status_code == 200, response.data
    assert response.json()["override_reason"] == "Emergency stock audit — back shortly"
