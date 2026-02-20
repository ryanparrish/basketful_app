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
def test_failed_validation_creates_failed_attempt_record():
    VoucherSettingFactory.create()
    participant = ParticipantFactory()
    account = participant.accountbalance
    account.base_balance = Decimal("30.00")
    account.save()

    hygiene = CategoryFactory(name="Hygiene")
    product = ProductFactory(category=hygiene, price=Decimal("20.00"))
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
    assert attempt.total_attempted == Decimal("20.00")
    assert attempt.food_total == Decimal("0.00")
    assert attempt.hygiene_total == Decimal("20.00")
    assert attempt.active_voucher_count >= 0
    assert attempt.validation_errors

