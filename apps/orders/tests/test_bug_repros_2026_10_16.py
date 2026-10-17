"""Reproduction tests for confirmed Basketful bugs (2026-10-16 review).

Each test asserts the CORRECT behavior and FAILS on the current code,
demonstrating the bug. Do NOT "fix" these tests to pass — fix the code.

Covers: H1, H2, H5, H9, M5, M9 (+ more as the fix pass proceeds).

Environment: run on SQLite via the test-only settings shim:
    DATABASE_URL="sqlite:////tmp/test_db.sqlite3" SECRET_KEY=x HASHIDS_SALT=y \
    DJANGO_SETTINGS_MODULE=apps.orders.tests.repro_sqlite_settings \
    python -m pytest apps/orders/tests/test_bug_repros_2026_10_16.py
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program
from apps.orders.models import Order, OrderItem
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    ProgramFactory,
    CategoryFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
    OrderFactory,
)

VALIDATE_CART_URL = "/api/v1/orders/validate-cart/"


@pytest.fixture
def singletons(db):
    """VoucherSetting + ProgramSettings singletons the code paths expect."""
    from core.models import ProgramSettings

    VoucherSettingFactory.create()
    ProgramSettings.get_settings()


def _account_with_vouchers(base_balance: Decimal, num_vouchers: int, stored_multiplier: int = 1):
    """Participant + account with `num_vouchers` grocery vouchers.

    Each voucher's STORED multiplier is `stored_multiplier` (the column
    _consume_vouchers reads); voucher_amnt == account.base_balance.
    """
    user = UserFactory()
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    account.base_balance = base_balance
    account.save(update_fields=["base_balance"])
    account.vouchers.all().delete()
    for _ in range(num_vouchers):
        VoucherFactory.create(
            account=account,
            state="applied",
            voucher_type="grocery",
            active=True,
            multiplier=stored_multiplier,
        )
    return user, participant, account


@pytest.mark.django_db
def test_h1_confirm_must_agree_with_validation_on_multiplier(monkeypatch, singletons):
    """H1 — voucher multiplier mismatch: validation vs confirmation disagree.

    apps/orders/models.py (_consume_vouchers._effective_amount) must use the
    multiplier the order was VALIDATED against at creation
    (Order.pause_multiplier_at_creation, set by OrderOrchestration) — not the
    live multiplier and not each voucher's stored column.

    Repro: gate open (live multiplier 2), two $50 vouchers, $150 order
    created pending with pause_multiplier_at_creation=2. Gate closes (live
    multiplier back to 1) before staff confirm. Confirming must still use
    the recorded 2 ($200 >= $150).

    Expected: confirm() succeeds.
    Actual (live-multiplier code): ValidationError("Order total $150.00
    exceeds available voucher balance $100.00") -> test FAILS,
    demonstrating H1 as refined in review.
    """
    from apps.account.utils import balance_utils
    from apps.account.utils.balance_utils import calculate_available_balance

    live = {"mult": 2}
    monkeypatch.setattr(
        balance_utils, "_get_current_pause_multiplier", lambda: live["mult"]
    )

    _, _, account = _account_with_vouchers(
        base_balance=Decimal("50.00"), num_vouchers=2, stored_multiplier=1
    )

    # Validation side at creation time — what the participant sees.
    assert calculate_available_balance(account) == Decimal("200")

    category = CategoryFactory(name="H1 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )
    # As OrderOrchestration.create_order does during the gate.
    order = Order(
        account=account, status="pending", pause_multiplier_at_creation=2
    )
    order.save()  # pending: full_clean runs the duplicate-guard only
    OrderItem.objects.create(order=order, product=product, quantity=3)  # $150
    assert order.total_price() == Decimal("150.00")

    # Gate closes before staff confirm: live multiplier drops to 1.
    live["mult"] = 1

    # Confirm must use the recorded creation-time multiplier (2), not the
    # live 1 and not the vouchers' stored 1.
    order.confirm()
    order.refresh_from_db()
    assert order.status == "confirmed"


@pytest.mark.django_db
def test_h2_resaving_order_item_does_not_reprice(singletons):
    """H2 — OrderItem.save() silently re-prices historical order lines.

    apps/orders/models.py (OrderItem.save) — self.price = product.price runs
    unconditionally on every save. Staff editing the quantity on an old
    confirmed order in admin (or any re-save) re-prices the line at today's
    product price, mutating the historical order total and everything
    downstream (_consume_vouchers, packing lists).

    Expected: re-saving a line keeps its original price; totals use
    price_at_order.
    Actual (current code): price is overwritten with the current product
    price -> test FAILS, demonstrating H2.
    """
    category = CategoryFactory(name="H2 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )
    _, _, account = _account_with_vouchers(
        base_balance=Decimal("100.00"), num_vouchers=2
    )
    order = Order(account=account, status="pending")
    order.save()
    item = OrderItem.objects.create(order=order, product=product, quantity=2)
    assert item.price == Decimal("10.00")
    assert item.price_at_order == Decimal("10.00")

    # Product price changes later; staff edits the line's quantity.
    product.price = Decimal("20.00")
    product.save()
    item.quantity = 3
    item.save()
    item.refresh_from_db()

    assert item.price == Decimal("10.00"), (
        f"historical line was re-priced to {item.price}; expected 10.00"
    )
    assert item.total_price() == Decimal("30.00")


@pytest.mark.django_db
def test_h3_staff_confirm_requires_explicit_bypass_flag(singletons):
    """H3 — staff confirm implicitly bypasses the balance check.

    apps/orders/api/views.py (confirm action, perform_update) —
    `if request.user.has_perm('orders.can_bypass_order_transitions'):
    order._bypass_balance_check = True` runs automatically for any holder of
    a permission named for *transitions*, not balances. _consume_vouchers
    then consumes vouchers even when the total exceeds the balance, logging
    only a WARNING — no explicit per-request intent required.

    Expected: without an explicit per-request flag the confirm fails (400);
    with {"bypass_balance": true} it succeeds and is audit-logged.
    Actual (current code): the flagless confirm succeeds -> test FAILS,
    demonstrating H3.
    """
    from django.contrib.auth.models import Permission, User as AuthUser

    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(codename="can_bypass_order_transitions")
    )
    staff = AuthUser.objects.get(pk=staff.pk)  # clear the permission cache

    category = CategoryFactory(name="H3 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )
    _, _, account = _account_with_vouchers(
        base_balance=Decimal("10.00"), num_vouchers=1, stored_multiplier=1
    )
    order = Order(account=account, status="pending")
    order.save()
    OrderItem.objects.create(order=order, product=product, quantity=1)  # $50 > $10

    client = APIClient()
    client.force_authenticate(user=staff)

    # No explicit flag: the balance check must hold -> 400.
    resp = client.post(f"/api/v1/orders/{order.id}/confirm/", {}, format="json")
    assert resp.status_code == 400, (
        f"flagless staff confirm of a short-balance order should 400, "
        f"got {resp.status_code}: {getattr(resp, 'data', None)}"
    )
    order.refresh_from_db()
    assert order.status == "pending"

    # Explicit flag: bypass works and is audit-logged.
    resp = client.post(
        f"/api/v1/orders/{order.id}/confirm/",
        {"bypass_balance": True},
        format="json",
    )
    assert resp.status_code == 200, f"explicit bypass confirm failed: {getattr(resp, 'data', None)}"
    order.refresh_from_db()
    assert order.status == "confirmed"


@pytest.mark.django_db
def test_h4_bulk_confirm_reports_per_order_failure(singletons):
    """H4 — bulk_update_status: one bad order nukes the whole batch.

    apps/orders/api/views.py (bulk_update_status) — everything runs inside
    one transaction.atomic() with no per-order try/except; order.confirm()
    raising ValidationError rolls back all orders and returns a single 400
    naming no order ID.

    Expected: 200 with per-order results — the good order confirms, the bad
    one stays pending and is reported with its error message.
    Actual (current code): 400, zero orders confirmed -> test FAILS,
    demonstrating H4.
    """
    staff = UserFactory(is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=staff)

    category = CategoryFactory(name="H4 Grocery")
    cheap = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )
    pricey = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )

    # Good order: $10 item against $100 balance.
    _, _, good_account = _account_with_vouchers(
        base_balance=Decimal("100.00"), num_vouchers=2
    )
    good_order = Order(account=good_account, status="pending")
    good_order.save()
    OrderItem.objects.create(order=good_order, product=cheap, quantity=1)

    # Bad order: $50 item against $10 balance.
    _, _, bad_account = _account_with_vouchers(
        base_balance=Decimal("10.00"), num_vouchers=1
    )
    bad_order = Order(account=bad_account, status="pending")
    bad_order.save()
    OrderItem.objects.create(order=bad_order, product=pricey, quantity=1)

    resp = client.post(
        "/api/v1/orders/bulk_update_status/",
        {"order_ids": [good_order.id, bad_order.id], "new_status": "confirmed"},
        format="json",
    )

    assert resp.status_code == 200, (
        "bulk confirm must not 400 when one order fails; "
        f"got {resp.status_code}: {getattr(resp, 'data', None)}"
    )
    good_order.refresh_from_db()
    bad_order.refresh_from_db()
    assert good_order.status == "confirmed"
    assert bad_order.status == "pending"
    failed = resp.data.get("failed_ids", {})
    assert bad_order.id in failed, (
        f"expected a per-order error for order {bad_order.id}: {resp.data}"
    )


@pytest.mark.django_db
def test_m1_validate_cart_pending_order_returns_proper_shape(singletons):
    """M1 — validate_cart returns a malformed 400 for participants with a
    pending order.

    apps/orders/api/views.py (validate_cart) — temp_order.save() triggers
    full_clean() → the duplicate-active-order guard raises ValidationError;
    only the _ValidationDone sentinel is caught, so the client gets a generic
    400 in DRF's error shape instead of the {valid, violations, balances, ...}
    shape the frontend cart drawer expects.

    Expected: 200 with the standard validation shape, valid=False, a
    violation explaining the active order, and balances still present.
    Actual (current code): 400 with a generic error shape -> test FAILS,
    demonstrating M1.
    """
    user = UserFactory(username="m1user")
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    # The participant already has a pending order.
    existing = Order(account=account, status="pending")
    existing.save()

    category = CategoryFactory(name="M1 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        VALIDATE_CART_URL,
        {"items": [{"product_id": product.id, "quantity": 1}]},
        format="json",
    )

    assert resp.status_code == 200, (
        f"validate_cart should return the standard shape for a participant "
        f"with a pending order, got {resp.status_code}: {getattr(resp, 'data', None)}"
    )
    data = resp.data
    assert {"valid", "violations", "balances", "limits", "rules_version"} <= set(data.keys()), (
        f"response missing standard keys: {sorted(data.keys())}"
    )
    assert data["valid"] is False
    assert any(
        "active order" in v["message"].lower() for v in data["violations"]
    ), f"expected an active-order violation: {data['violations']}"
    assert "available" in data["balances"]


@pytest.mark.django_db
def test_m2_admin_full_clean_confirmed_order_no_500(singletons):
    """M2 — admin edit of a confirmed order → 500 (AttributeError).

    Order.clean()'s _old_status skip is only set inside Order.save();
    Django admin's ModelForm calls full_clean() directly. Two compounding
    bugs: (a) Voucher.validate_vouchers calls Order.total_price(queryset) —
    an instance method receiving a QuerySet → AttributeError, which escapes
    the `except ValidationError`; (b) without the _old_status skip, balance
    re-validation runs against consumed (zero-balance) vouchers → false
    positive ValidationError.

    Expected: full_clean() on a confirmed order passes cleanly (what the
    save() path already guarantees).
    Actual (current code): AttributeError -> test FAILS, demonstrating M2.
    """
    _, _, account = _account_with_vouchers(
        base_balance=Decimal("50.00"), num_vouchers=2, stored_multiplier=1
    )
    category = CategoryFactory(name="M2 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )
    order = Order(account=account, status="pending")
    order.save()
    OrderItem.objects.create(order=order, product=product, quantity=2)  # $100
    order.confirm()
    order.refresh_from_db()
    assert order.status == "confirmed"

    # What Django admin's ModelForm does on edit: full_clean() directly,
    # bypassing Order.save() (which is where _old_status is normally set).
    admin_order = Order.objects.get(pk=order.pk)
    try:
        admin_order.full_clean()
    except AttributeError as exc:
        pytest.fail(f"full_clean() raised AttributeError (500 in admin): {exc}")


@pytest.mark.django_db
def test_m6_cancel_action_handles_save_errors(singletons):
    """M6 — cancel() action has zero exception handling.

    apps/orders/api/views.py (cancel) — any exception from Order.save()
    (DB error, _restore_on_cancel, audit-log write) escapes to the
    middleware's generic 500; staff can't tell whether the cancel applied
    (the DB is protected by atomicity, the response isn't).

    Expected: a save failure returns a controlled JSON error and the atomic
    block guarantees the cancel did NOT apply.
    Actual (current code): the raw exception propagates -> test FAILS
    (errors), demonstrating M6.
    """
    from unittest import mock

    staff = UserFactory(is_staff=True, is_superuser=True)
    _, _, account = _account_with_vouchers(
        base_balance=Decimal("50.00"), num_vouchers=1
    )
    order = Order(account=account, status="pending")
    order.save()

    client = APIClient()
    client.force_authenticate(user=staff)

    with mock.patch(
        "apps.orders.models.Order.save", side_effect=RuntimeError("db gone")
    ):
        resp = client.post(f"/api/v1/orders/{order.id}/cancel/", {}, format="json")

    assert resp.status_code == 500
    assert resp.data["error"] == (
        "An unexpected error occurred while cancelling the order."
    )
    order.refresh_from_db()
    assert order.status == "pending"


@pytest.mark.django_db
def test_m7_redis_outage_does_not_lie_or_punish(mocker, singletons):
    """M7 — Redis outage produces a lying error and punishes the user.

    apps/orders/utils/order_services.py (distributed_order_lock) fails the
    lock closed on Redis errors, yielding lock_acquired=False —
    indistinguishable from contention. apps/orders/utils/order_utils.py then
    tells every participant "Another order is being processed" (false),
    returns 400, and stacks exponential backoff for an infrastructure outage.

    Expected: on lock-backend failure the error is truthful ("temporarily
    unavailable") and no backoff is accrued.
    Actual (current code): "Another order is being processed" + backoff ->
    test FAILS, demonstrating M7.
    """
    from unittest import mock
    from apps.orders.utils.order_utils import OrderOrchestration
    from apps.orders.utils.order_validation import OrderItemData

    _, _, account = _account_with_vouchers(
        base_balance=Decimal("100.00"), num_vouchers=2
    )
    user = account.participant.user
    category = CategoryFactory(name="M7 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )

    mock_increment = mocker.patch(
        "apps.orders.utils.order_utils.increment_failure_count"
    )

    with mock.patch(
        "apps.orders.utils.order_services.cache.add",
        side_effect=Exception("redis down"),
    ):
        with pytest.raises(ValidationError) as exc_info:
            OrderOrchestration().create_order(
                account=account,
                order_items_data=[OrderItemData(product=product, quantity=1)],
                user=user,
            )

    message = str(exc_info.value).lower()
    assert "temporarily unavailable" in message, (
        f"expected truthful outage message, got: {exc_info.value}"
    )
    assert "another order is being processed" not in message
    mock_increment.assert_not_called()


@pytest.mark.django_db
def test_m8_hourly_and_daily_throttles_enforced(singletons):
    """M8 — throttle limits documented but not enforced.

    apps/orders/api/throttles.py docstring promises 3/min, 10/hr, 50/day but
    core/settings.py defined only 'order_submission': '3/minute', and DRF
    supports one rate per throttle class — so a script could submit 3/min
    indefinitely (~4,320/day vs the documented 50).

    Expected: the hourly throttle allows 10 requests and blocks the 11th;
    the daily throttle allows 50 and blocks the 51st.
    Actual (current code): the hourly/daily classes and rates don't exist ->
    test FAILS, demonstrating M8.
    """
    from django.core.cache import cache
    from rest_framework.test import APIRequestFactory

    from apps.orders.api.throttles import (
        OrderSubmissionHourlyThrottle,
        OrderSubmissionDailyThrottle,
    )

    cache.clear()
    user = UserFactory(username="m8user")
    factory = APIRequestFactory()

    def allowed_count(throttle, n):
        count = 0
        for _ in range(n):
            request = factory.post("/api/v1/orders/")
            request.user = user
            if throttle.allow_request(request, None):
                count += 1
        return count

    assert allowed_count(OrderSubmissionHourlyThrottle(), 11) == 10, (
        "hourly throttle should allow exactly 10 submissions per hour"
    )
    cache.clear()
    assert allowed_count(OrderSubmissionDailyThrottle(), 51) == 50, (
        "daily throttle should allow exactly 50 submissions per day"
    )


@pytest.mark.django_db
def test_m10_order_item_writes_not_exposed(singletons):
    """M10 — POST /order-items/ can never succeed — always 500.

    OrderItemCreateSerializer has no `order` field but OrderItem.order is
    NOT NULL, so every create → IntegrityError → generic 500. Order items
    are created through the order-creation flow, never this endpoint.

    Expected: write actions aren't exposed (405); reads keep working.
    Actual (current code): POST → 500 -> test FAILS, demonstrating M10.
    """
    staff = UserFactory(is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=staff)
    category = CategoryFactory(name="M10 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )

    resp = client.post(
        "/api/v1/order-items/",
        {"product": product.id, "quantity": 1},
        format="json",
    )
    assert resp.status_code == 405, (
        f"order-item writes should not be exposed, got {resp.status_code}"
    )

    # Reads still work.
    resp = client.get("/api/v1/order-items/", format="json")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_l15_login_uses_captcha_after_failures():
    """L15 — custom_login_view (captcha-after-3-failures) never wired.

    core/urls.py — /login/ uses plain auth_views.LoginView with no rate
    limiting; apps/account/views.py custom_login_view (captcha after 3
    failures) is dead code.

    Expected: POSTing bad credentials 3 times makes the 4th GET show a
    captcha (show_captcha=True in context).
    Actual (current code): plain LoginView, no captcha ever -> test FAILS,
    demonstrating L15.
    """
    from django.test import Client

    UserFactory(username="l15user", password="s3cret-pass")
    client = Client()

    # 3 failed attempts.
    for _ in range(3):
        client.post("/login/", {"username": "l15user", "password": "wrong"})

    resp = client.get("/login/")
    assert resp.context is not None, "login page did not render a template"
    assert resp.context.get("show_captcha") is True, (
        "expected captcha after 3 failures (custom_login_view), "
        "got plain LoginView"
    )


@pytest.mark.django_db
def test_l1_clone_uses_valid_status_field(mocker):
    """L1 — OrderOrchestration.clone() passes status_type= (no such field).

    apps/orders/utils/order_utils.py:361 — Order.objects.create(...,
    status_type=status) raises TypeError ('status_type' is an invalid
    keyword argument). No callers; latent, but the fix is one word.

    Expected: clone() creates the new order with the given status.
    Actual (current code): TypeError -> test FAILS, demonstrating L1.
    """
    from apps.orders.utils.order_utils import OrderOrchestration

    participant = ParticipantFactory()
    order = OrderFactory(account=participant.accountbalance)
    product = ProductFactory(price=Decimal("5.00"))
    OrderItem.objects.create(order=order, product=product, quantity=2)

    # Cancel the original so the clone doesn't trip the duplicate-order guard.
    order.status = "cancelled"
    order.save(update_fields=["status"])

    orch = OrderOrchestration()
    orch.order = order
    new_order = orch.clone(status="pending")

    assert new_order.status == "pending"
    assert new_order.items.count() == 1


@pytest.mark.django_db
def test_l7_orderitem_full_clean_before_write(singletons):
    """L7 — OrderItem.save() calls full_clean() AFTER the write.

    apps/orders/models.py — super().save() then self.full_clean(): a
    validation failure leaves the bad row committed ("validation theater").

    Expected: full_clean runs before the INSERT; invalid rows never persist.
    Actual (current code): row persists even when clean() raises -> test
    FAILS, demonstrating L7.
    """
    from django.core.exceptions import ValidationError

    participant1 = ParticipantFactory()
    participant2 = ParticipantFactory()
    order = OrderFactory(account=participant1.accountbalance)
    product = ProductFactory(price=Decimal("5.00"))

    # Create a second order for a DIFFERENT participant; then try to move
    # the item to it via save(). clean() forbids moving an OrderItem
    # between orders.
    order2 = OrderFactory(account=participant2.accountbalance)
    item = OrderItem.objects.create(order=order, product=product, quantity=1)
    item.order = order2

    with pytest.raises(ValidationError):
        item.save()

    # The bad move must not have persisted.
    item.refresh_from_db()
    assert item.order_id == order.id, (
        f"invalid OrderItem move was committed (order_id={item.order_id})"
    )


@pytest.mark.django_db
def test_l10_add_orders_rejects_non_integer_ids(singletons):
    """L10 — add_orders/remove_orders with non-integer IDs → 500 on Postgres.

    apps/orders/api/views.py — Order.objects.filter(id__in=order_ids) with
    no validation; Postgres raises DataError on WHERE id IN ('abc') → 500.
    (SQLite silently returns empty, so this test demonstrates the missing
    input validation rather than the 500 itself.)

    Expected: 400 for non-integer IDs.
    Actual (current code): 200, garbage silently ignored -> test FAILS,
    demonstrating L10.
    """
    from apps.orders.models import CombinedOrder

    staff = UserFactory(is_staff=True, is_superuser=True)
    program = ProgramFactory(name="L10 Program")
    co = CombinedOrder.objects.create(program=program)

    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.post(
        f"/api/v1/combined-orders/{co.id}/add_orders/",
        {"order_ids": ["abc"]},
        format="json",
    )
    assert resp.status_code == 400, (
        f"non-integer order_ids should 400, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_l9_create_with_packing_bad_program_returns_404(singletons):
    """L9 — create_with_packing with a nonexistent program → 500 not 404.

    apps/orders/api/views.py — Program.objects.get(id=program_id) with no
    DoesNotExist catch.

    Expected: 404.
    Actual (current code): 500 -> test FAILS, demonstrating L9.
    """
    staff = UserFactory(is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=staff)

    resp = client.post(
        "/api/v1/combined-orders/create-with-packing/",
        {"program_id": 999999, "order_ids": [1]},
        format="json",
    )
    assert resp.status_code == 404, (
        f"nonexistent program should 404, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_l8_analytics_limit_abc_returns_400_not_500(singletons):
    """L8 — Staff analytics endpoints 500 on ?limit=abc.

    apps/orders/api/views.py — product_consumption (and 4 siblings) do
    int(request.query_params.get('limit', ...)) with no ValueError catch.

    Expected: 400 with a clear error.
    Actual (current code): 500 -> test FAILS, demonstrating L8.
    """
    staff = UserFactory(is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_authenticate(user=staff)

    resp = client.get("/api/v1/orders/product-consumption/?limit=abc")
    assert resp.status_code == 400, (
        f"?limit=abc should 400, got {resp.status_code}"
    )


@pytest.mark.django_db
def test_m17_duplicate_submission_does_not_trigger_backoff(mocker):
    """M17 — Poisoned retries also grow the backoff counter.

    apps/orders/utils/order_utils.py — the duplicate-submission path calls
    increment_failure_count() before raising. A legitimate double-submit
    (already safely rejected by idempotency) stacks 2^n-second backoffs
    onto the user. The lock-contention path keeps its backoff (legitimate
    thundering-herd protection); the duplicate path should not punish.

    Expected: duplicate submission raises ValidationError WITHOUT calling
    increment_failure_count.
    Actual (current code): increment_failure_count called -> test FAILS,
    demonstrating M17.
    """
    from apps.orders.utils.order_utils import (
        OrderOrchestration, check_duplicate_submission,
    )
    from apps.orders.utils.order_validation import OrderItemData

    _, _, account = _account_with_vouchers(
        base_balance=Decimal("100.00"), num_vouchers=2
    )
    user = account.participant.user
    category = CategoryFactory(name="M17 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("10.00"), quantity_in_stock=100
    )

    # Simulate a poisoned/duplicate idempotency key already in cache.
    idempotency_key = "m17-duplicate-key"
    mocker.patch(
        "apps.orders.utils.order_utils.check_duplicate_submission",
        return_value=True,
    )
    # Force the orchestrator to use our key.
    mocker.patch(
        "apps.orders.utils.order_utils.generate_idempotency_key",
        return_value=idempotency_key,
    )
    mock_increment = mocker.patch(
        "apps.orders.utils.order_utils.increment_failure_count"
    )

    with pytest.raises(ValidationError) as exc_info:
        OrderOrchestration().create_order(
            account=account,
            order_items_data=[OrderItemData(product=product, quantity=1)],
            user=user,
        )

    assert "duplicate" in str(exc_info.value).lower()
    mock_increment.assert_not_called()


@pytest.mark.django_db
def test_m15_order_window_enforced_on_create(singletons):
    """M15 — Weekly ordering window never enforced server-side on submission.

    core/utils.py can_place_order() is computed and displayed, but neither
    the DRF create endpoint nor submit_order calls it; only order_detail's
    duplicate-POST path blocks. A participant can POST an order with the
    window force-closed.

    Expected: 400 when the participant's program window is closed.
    Actual (current code): 201 — order created -> test FAILS, demonstrating M15.

    Ambiguous call (flagged for Ryan): the window is treated as a real gate
    here (matching the frontend hiding + the duplicate-POST block + the
    force-open "escape hatch" semantics). Staff are exempt — they act on
    behalf of participants and have the force-open override.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.core.cache import cache
    from core.models import ProgramWindowOverride

    # Throttle state persists across tests in locmem cache; user IDs are
    # reused after rollback. Clear it so the window check (not the daily
    # throttle) is what we exercise.
    cache.clear()

    participant = ParticipantFactory()
    user = participant.user
    product = ProductFactory(price=Decimal("5.00"))

    # Force the program window closed.
    ProgramWindowOverride.objects.create(
        program=participant.program,
        force_status="closed",
        expires_at=timezone.now() + timedelta(days=1),
        reason="M15 test",
    )

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        "/api/v1/orders/",
        {"items": [{"product": product.id, "quantity": 1}]},
        format="json",
    )
    assert resp.status_code == 400, (
        f"order with closed window should 400, got {resp.status_code}: "
        f"{getattr(resp, 'data', None)}"
    )


@pytest.mark.django_db
def test_m14_pause_created_early_flags_vouchers_at_double_week_gate():
    """M14 — Pauses created >14 days out never get voucher flags during the
    double week.

    apps/lifeskills/signals.py — the "outside ordering window" branch calls
    schedule_voucher_tasks(vouchers, activate_time=pause_start, ...): flags
    are scheduled to activate when the pause STARTS (the no-order week), not
    when it ENTERS the 10-14-day double-week gate. Participants creating
    double orders during the double week get no voucher flags.

    Expected: activation is scheduled for pause_start - 14 days with the
    pause-duration multiplier.
    Actual (current code): activation scheduled at pause_start -> test FAILS,
    demonstrating M14.
    """
    from datetime import timedelta
    from decimal import Decimal
    from unittest import mock
    from django.utils import timezone
    from apps.lifeskills.models import ProgramPause
    from apps.account.models import Participant, AccountBalance
    from apps.voucher.models import Voucher

    program = ProgramFactory(name="M14 Program")
    participant = Participant.objects.create(
        name="M14 Participant", email="m14@example.com",
        program=program, active=True, adults=2, children=1,
    )
    account, _ = AccountBalance.objects.get_or_create(
        participant=participant, defaults={"base_balance": Decimal("100.0")}
    )
    account.vouchers.all().delete()
    Voucher.objects.create(
        account=account, active=True, voucher_type="grocery", state="applied"
    )

    now = timezone.now()
    pause_start = now + timedelta(days=20)
    pause_end = pause_start + timedelta(days=7)

    with mock.patch(
        "apps.voucher.tasks.voucher_scheduling.update_voucher_flag_task"
    ) as mock_task:
        ProgramPause.objects.create(
            pause_start=pause_start, pause_end=pause_end, reason="M14"
        )

    activate_calls = [
        c for c in mock_task.apply_async.call_args_list
        if c.kwargs.get("kwargs", {}).get("activate")
    ]
    assert activate_calls, "no voucher activation was scheduled at all"
    eta = activate_calls[0].kwargs["eta"]
    expected = pause_start - timedelta(days=14)
    assert abs((eta - expected).total_seconds()) < 120, (
        f"activation scheduled at {eta}, expected the double-week gate ~{expected}"
    )
    multiplier = activate_calls[0].kwargs["kwargs"]["multiplier"]
    assert multiplier == 2, f"expected duration multiplier 2, got {multiplier}"


@pytest.mark.django_db
def test_m13_iso_year_used_for_combined_order_week_year(singletons):
    """M13 — ISO week stored with calendar year → year-boundary collisions.

    CombinedOrder.save() (and three sibling write sites in
    combined_order_helper.py) store week = now.isocalendar()[1] but
    year = now.year instead of now.isocalendar()[0]. Jan 1–2, 2028
    (ISO 2027-W52) and Dec 25–31, 2028 (ISO 2028-W52) both store (52, 2028):
    December's get_or_create silently merges into January's stale row (wrong
    warehouse list) or raises "already exists for this week".

    Expected: the stored year is the ISO year (2027 for Jan 1, 2028).
    Actual (current code): calendar year 2028 -> test FAILS, demonstrating M13.
    """
    from freezegun import freeze_time
    from apps.orders.models import CombinedOrder

    program = ProgramFactory(name="M13 Program")

    with freeze_time("2028-01-01"):  # Saturday → ISO 2027-W52
        co = CombinedOrder(program=program)
        co.save()
        assert (co.week, co.year) == (52, 2027), (
            f"expected ISO (52, 2027), got ({co.week}, {co.year})"
        )

    with freeze_time("2028-12-30"):  # Saturday → ISO 2028-W52
        co2 = CombinedOrder(program=program)
        co2.save()
        assert (co2.week, co2.year) == (52, 2028), (
            f"expected ISO (52, 2028), got ({co2.week}, {co2.year})"
        )


@pytest.mark.django_db
def test_h9_parent_combined_order_survives_child(singletons):
    """H9 — weekly combined-order job crashes: parent create hits IntegrityError.

    apps/orders/models.py:690-786 — UniqueConstraint on (program, week, year)
    does NOT include is_parent.
    apps/orders/tasks/helper/combined_order_helper.py:123-188 —
    create_child_combined_orders() get_or_creates (program, week, year,
    is_parent=False); create_parent_combined_order() then get_or_creates
    (program, week, year, is_parent=True). The parent lookup misses (the row
    has is_parent=False), the create violates the unique constraint, and
    get_or_create's retry-get still misses -> IntegrityError propagates.

    Expected: parent combined order is created, no IntegrityError.
    Actual (current code): IntegrityError -> test FAILS, demonstrating H9.
    """
    from django.db.models import Model
    from apps.orders.tasks.helper.combined_order_helper import (
        create_child_combined_orders,
        create_parent_combined_order,
    )

    program = ProgramFactory(name="H9 Program")
    user = UserFactory(username="h9user")
    participant = ParticipantFactory(user=user, program=program)
    account = participant.accountbalance

    order = Order(account=account, status="pending")
    Model.save(order)  # bypass full_clean like the existing test helper

    children = create_child_combined_orders(program, [order], packer=None)
    assert len(children) == 1
    assert children[0].is_parent is False

    # This is the Monday 6 AM crash: must not raise.
    parent = create_parent_combined_order(program, children, packer=None)
    assert parent.is_parent is True


def test_m5a_failed_attempt_must_not_poison_retry():
    """M5a — idempotency incoherence: a FAILED attempt poisons the retry.

    apps/orders/utils/order_services.py — generate_idempotency_key embeds a
    minute-precision timestamp ('%Y-%m-%d %H:%M') while check_duplicate_
    submission advertises a 300s TTL. The view marks the key BEFORE
    validation runs, so when validation fails and the participant retries
    with the identical cart in the same minute, the retry is wrongly flagged
    "Duplicate order submission detected".

    Expected: the retry is NOT flagged (no order was created).
    Actual (current code): returns True -> test FAILS, demonstrating M5.
    """
    from django.core.cache import cache
    from apps.orders.utils.order_services import (
        generate_idempotency_key,
        check_duplicate_submission,
    )

    cache.clear()
    cart = [{"product_id": 1, "quantity": 2}]

    # First attempt: the view marks the key, then validation FAILS.
    key = generate_idempotency_key(participant_id=4242, cart_items=cart)
    assert check_duplicate_submission(key) is False

    # Retry, same cart, same minute -> identical key (no order was created).
    retry_key = generate_idempotency_key(participant_id=4242, cart_items=cart)
    assert retry_key == key
    assert check_duplicate_submission(retry_key) is False


def test_m5b_key_changes_across_minute_boundary():
    """M5b — idempotency key must not depend on wall-clock time at all.

    Review #107: 5-minute wall-clock buckets kept the boundary bug, just
    every 5 minutes instead of every minute (10:04:59 vs 10:05:01 still got
    different keys; the old test passed only because its two times fell in
    the same bucket). The key is now participant + cart only; the 300s cache
    TTL defines the dedup window.

    Expected: identical keys regardless of when they are generated — the
    function no longer reads the clock, so the old minute/bucket boundaries
    (10:00:59 vs 10:01:01, 10:04:59 vs 10:05:01) cannot split it.
    """
    import apps.orders.utils.order_services as order_services

    cart = [{"product_id": 1, "quantity": 2}]
    keys = {
        order_services.generate_idempotency_key(participant_id=4242, cart_items=cart)
        for _ in range(3)
    }
    # Sanity: the implementation must not consult the wall clock at all.
    assert "datetime" not in dir(order_services), (
        "generate_idempotency_key must not depend on wall-clock time"
    )
    assert len(keys) == 1


@pytest.mark.django_db
def test_m9_validate_cart_malformed_participant_id_is_400(singletons):
    """M9 — validate_cart 500s on malformed input where create 400s cleanly.

    apps/orders/api/views.py (validate_cart): Participant.objects.get(
    id=participant_id) with participant_id="abc" raises ValueError, which is
    NOT caught (only Participant.DoesNotExist is) -> 500 in production.

    Expected: clean 400 response.
    Actual (current code): ValueError propagates (500) -> test FAILS,
    demonstrating M9.
    """
    user = UserFactory(username="m9user")
    client = APIClient()
    client.force_authenticate(user=user)

    try:
        response = client.post(
            VALIDATE_CART_URL,
            {"participant_id": "abc", "items": []},
            format="json",
        )
    except ValueError as exc:
        pytest.fail(
            "validate_cart raised ValueError instead of returning 400 "
            f"(this is a 500 in production): {exc}"
        )
    assert response.status_code == 400, (
        f"expected 400 for malformed participant_id, got {response.status_code}"
    )


@pytest.mark.django_db
def test_h4_failed_bulk_confirm_writes_no_bypass_warning(singletons):
    """Review #107 (apps/orders/api/views.py:446 blocker): a bulk-confirmed
    order that FAILS must not leave a spurious "Transition bypass … →
    confirmed" WARNING in the audit log.

    A pending → confirmed bulk update by a can_bypass staffer routes through
    the bypass path, but if order.confirm() then raises (over balance), the
    transition never happened — logging a bypass WARNING for it is wrong
    and makes staff think it confirmed.
    """
    from apps.log.models import OrderValidationLog

    staff = UserFactory(is_staff=True, is_superuser=True)  # all perms incl. bypass
    client = APIClient()
    client.force_authenticate(user=staff)

    category = CategoryFactory(name="H4 Audit Grocery")
    pricey = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )

    # Bad order: $50 item against $10 balance — confirm() will fail.
    _, _, bad_account = _account_with_vouchers(
        base_balance=Decimal("10.00"), num_vouchers=1
    )
    bad_order = Order(account=bad_account, status="pending")
    bad_order.save()
    OrderItem.objects.create(order=bad_order, product=pricey, quantity=1)

    resp = client.post(
        "/api/v1/orders/bulk_update_status/",
        {"order_ids": [bad_order.id], "new_status": "confirmed"},
        format="json",
    )
    assert resp.status_code == 200
    assert bad_order.id in resp.data.get("failed_ids", {}), (
        f"expected the bad order to fail: {resp.data}"
    )
    bad_order.refresh_from_db()
    assert bad_order.status == "pending"

    spurious = OrderValidationLog.objects.filter(
        order=bad_order,
        log_type=OrderValidationLog.WARNING,
        message__contains="Transition bypass",
    )
    assert not spurious.exists(), (
        "failed confirm must not leave a bypass WARNING in the audit log: "
        f"{list(spurious.values_list('message', flat=True))}"
    )


@pytest.mark.django_db
def test_pause_signal_near_term_pause_gets_immediate_activation(mocker):
    """Review #107 (apps/lifeskills/signals.py:214): a pause less than 10
    days away must take the immediate-activation path, not the
    future-scheduling path.

    Old code: the else branch scheduled activation at pause_start - 14d,
    which is already past for a near-term pause, so flags turned on
    immediately with NO smart deactivation (stayed on until pause_end).
    New code: days_until_start <= 14 takes the immediate path with
    earliest-window-close deactivation.
    """
    from django.utils import timezone
    from datetime import timedelta
    import apps.lifeskills.signals as pause_signals
    from apps.lifeskills.models import ProgramPause

    # Signal exits early without active vouchers; give it one.
    _account_with_vouchers(base_balance=Decimal("50.00"), num_vouchers=1)

    mock_immediate = mocker.patch.object(
        pause_signals.update_voucher_flag_task, "delay"
    )
    mock_scheduled = mocker.patch.object(pause_signals, "schedule_voucher_tasks")

    now = timezone.now()
    ProgramPause.objects.create(
        pause_start=now + timedelta(days=5),
        pause_end=now + timedelta(days=12),
        reason="near-term test pause",
    )

    assert mock_immediate.called, (
        "a pause 5 days out must take the immediate-activation path"
    )
    assert not mock_scheduled.called, (
        "a pause 5 days out must NOT take the future-scheduling path"
    )
