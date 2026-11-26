"""
#141: the pause multiplier is read live everywhere; nothing stores a copy.

No test here runs a Celery task or flags a voucher: creating (or archiving)
a pause is enough for every reader to follow it.
"""
import importlib
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.account.utils.balance_utils import _get_current_pause_multiplier
from apps.lifeskills.models import ProgramPause
from apps.lifeskills.tasks.program_pause import archive_ended_pauses
from apps.lifeskills.utils import active_pause, current_pause_multiplier
from apps.orders.tests.factories import (
    ParticipantFactory,
    UserFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.pantry.models import CategoryLimitValidator


def create_pause(starts_in_days, lasts_days, reason):
    pause_start = timezone.now() + timedelta(days=starts_in_days)
    return ProgramPause.objects.create(
        pause_start=pause_start,
        pause_end=pause_start + timedelta(days=lasts_days),
        reason=reason,
    )


@pytest.fixture
def staff_client():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=True))
    return client


@pytest.mark.django_db
class TestActivePause:

    def test_no_pause_means_multiplier_1(self):
        assert active_pause() is None
        assert current_pause_multiplier() == 1

    def test_pause_outside_its_window_does_not_count(self):
        create_pause(starts_in_days=30, lasts_days=7, reason="Far off")
        assert active_pause() is None

    def test_pause_in_its_window_counts(self):
        pause = create_pause(starts_in_days=12, lasts_days=7, reason="Spring break")
        assert active_pause() == pause
        assert current_pause_multiplier() == 2

    def test_overlapping_windows_pick_the_higher_multiplier(self):
        create_pause(starts_in_days=11, lasts_days=7, reason="Short")
        extended = create_pause(starts_in_days=13, lasts_days=20, reason="Extended")
        assert active_pause() == extended
        assert current_pause_multiplier() == 3

    def test_archived_pause_does_not_count(self):
        pause = create_pause(starts_in_days=12, lasts_days=7, reason="Archived")
        pause.archive()
        assert active_pause() is None


@pytest.mark.django_db
class TestReadersAgree:
    """Balance, category limits and order creation share one helper."""

    def test_in_progress_pause_does_not_hide_a_pause_in_its_window(self):
        # Before #141 the category-limit helper returned (1, ...) for an
        # in-progress pause and never looked at the double-week pause, so
        # orders stamped 1x while the balance showed 2x.
        create_pause(starts_in_days=-1, lasts_days=4, reason="Happening now")
        create_pause(starts_in_days=12, lasts_days=7, reason="Next break")

        assert _get_current_pause_multiplier() == 2
        assert CategoryLimitValidator._get_active_pause_multiplier() == (2, "Next break")

    def test_category_limits_follow_a_new_pause_immediately(self):
        assert CategoryLimitValidator._get_active_pause_multiplier() == (1, None)
        create_pause(starts_in_days=12, lasts_days=7, reason="Break")
        # No 5-minute cache: the next read sees the pause.
        assert CategoryLimitValidator._get_active_pause_multiplier() == (2, "Break")


@pytest.mark.django_db
class TestVoucherApiPauseMultiplier:

    @pytest.fixture
    def account(self):
        VoucherSettingFactory.create()
        account = ParticipantFactory().accountbalance
        account.vouchers.all().delete()
        return account

    def test_detail_follows_the_live_pause(self, staff_client, account):
        voucher = VoucherFactory(account=account, state="applied", voucher_type="grocery")
        url = f"/api/v1/vouchers/{voucher.id}/"

        assert staff_client.get(url).data["pause_multiplier"] == 1

        create_pause(starts_in_days=12, lasts_days=7, reason="Break")
        response = staff_client.get(url)
        assert response.data["pause_multiplier"] == 2
        assert "program_pause_flag" not in response.data

    def test_only_doubled_vouchers_show_the_multiplier(self, staff_client, account):
        applied = VoucherFactory(account=account, state="applied", voucher_type="grocery")
        consumed = VoucherFactory(account=account, state="consumed", voucher_type="grocery")
        hygiene = VoucherFactory(account=account, state="applied", voucher_type="hygiene")
        create_pause(starts_in_days=12, lasts_days=7, reason="Break")

        rows = staff_client.get("/api/v1/vouchers/", {"page_size": 100}).data["results"]
        multiplier_by_id = {row["id"]: row["pause_multiplier"] for row in rows}

        assert multiplier_by_id[applied.id] == 2
        assert multiplier_by_id[consumed.id] == 1
        assert multiplier_by_id[hygiene.id] == 1

    def test_list_looks_up_pauses_once(self, staff_client, account):
        for _ in range(5):
            VoucherFactory(account=account, state="applied", voucher_type="grocery")
        create_pause(starts_in_days=12, lasts_days=7, reason="Break")

        with CaptureQueriesContext(connection) as queries:
            response = staff_client.get("/api/v1/vouchers/")
        assert response.status_code == 200

        pause_queries = [q for q in queries if "food_orders_programpause" in q["sql"]]
        assert len(pause_queries) == 1


@pytest.mark.django_db
class TestArchiveEndedPauses:

    def test_archives_only_ended_pauses(self):
        ended = create_pause(starts_in_days=-10, lasts_days=3, reason="Ended")
        upcoming = create_pause(starts_in_days=12, lasts_days=7, reason="Upcoming")

        assert archive_ended_pauses() == 1

        ended.refresh_from_db()
        upcoming.refresh_from_db()
        assert ended.archived and ended.archived_at is not None
        assert not upcoming.archived

    def test_beat_row_is_pointed_at_the_archive_task(self):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        PeriodicTask.objects.create(
            name="cleanup-expired-pause-flags",
            task="apps.lifeskills.tasks.program_pause.cleanup_expired_pause_flags",
            crontab=CrontabSchedule.objects.create(hour="3", minute="0"),
        )
        migration = importlib.import_module(
            "apps.lifeskills.migrations.0009_rename_pause_cleanup_beat_task"
        )

        migration.point_beat_at_archive_task(django_apps, None)

        row = PeriodicTask.objects.get()
        assert row.name == "archive-ended-pauses"
        assert row.task == "apps.lifeskills.tasks.program_pause.archive_ended_pauses"
