from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.orders.models import FailedOrderAttempt, OrderItemData
from apps.orders.tests.factories import (
    CategoryFactory,
    ProductFactory,
    ParticipantFactory,
    VoucherSettingFactory,
)
from apps.orders.utils.order_services import distributed_order_lock
from apps.orders.utils.order_utils import OrderOrchestration


@pytest.mark.django_db
def test_distributed_order_lock_propagates_validation_error():
    with pytest.raises(ValidationError, match="test validation"):
        with distributed_order_lock(participant_id=999999, timeout=10) as acquired:
            assert acquired is True
            raise ValidationError("test validation")


@pytest.mark.django_db
def test_failed_validation_creates_failed_attempt_record(grace_off):
    VoucherSettingFactory.create()
    participant = ParticipantFactory()
    account = participant.accountbalance
    account.base_balance = Decimal("30.00")
    account.save()

    # Force a deterministic hygiene validation failure.
    hygiene_balance = account.hygiene_balance
    failing_price = hygiene_balance + Decimal("0.01")
    assert failing_price > account.hygiene_balance

    hygiene = CategoryFactory(name="Hygiene")
    product = ProductFactory(category=hygiene, price=failing_price)
    items = [OrderItemData(product=product, quantity=1)]

    orchestration = OrderOrchestration()

    with pytest.raises(ValidationError):
        orchestration.create_order(
            account=account,
            order_items_data=items,
            user=participant.user,
            request_meta={"ip": "127.0.0.1", "user_agent": "pytest"},
        )

    attempt = FailedOrderAttempt.objects.filter(participant=participant).latest("created_at")
    assert attempt.total_attempted == failing_price
    assert attempt.food_total == Decimal("0.00")
    assert attempt.hygiene_total == failing_price
    assert attempt.active_voucher_count >= 0
    assert attempt.validation_errors


@pytest.mark.django_db
def test_failed_attempt_records_the_live_pause(grace_off):
    """#141: pause info comes from the live pause, not a flagged voucher."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.lifeskills.models import ProgramPause

    VoucherSettingFactory.create()
    participant = ParticipantFactory()
    account = participant.accountbalance

    pause_start = timezone.now() + timedelta(days=12)
    ProgramPause.objects.create(
        pause_start=pause_start,
        pause_end=pause_start + timedelta(days=7),
        reason="Spring break",
    )

    hygiene = CategoryFactory(name="Hygiene")
    product = ProductFactory(category=hygiene, price=account.hygiene_balance + Decimal("0.01"))

    with pytest.raises(ValidationError):
        OrderOrchestration().create_order(
            account=account,
            order_items_data=[OrderItemData(product=product, quantity=1)],
            user=participant.user,
            request_meta={"ip": "127.0.0.1", "user_agent": "pytest"},
        )

    attempt = FailedOrderAttempt.objects.filter(participant=participant).latest("created_at")
    assert attempt.program_pause_active is True
    assert attempt.voucher_multiplier == 2
    assert attempt.program_pause_name == "Spring break"
