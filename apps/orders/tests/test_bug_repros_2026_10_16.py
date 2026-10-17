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

    apps/orders/models.py:490-495 (_consume_vouchers._effective_amount uses
    each voucher's STORED multiplier column) vs
    apps/account/utils/balance_utils.py:44-54 (calculate_available_balance
    uses the LIVE _get_current_pause_multiplier()).

    Repro: two $50 vouchers with stored multiplier=1 while the live pause
    multiplier is 2. Validation reports $200 available, but confirming a
    $150 order raises ValidationError("Order total $150.00 exceeds available
    voucher balance $100.00") and the order is stuck in pending.

    Expected: confirm() succeeds (it agrees with validation).
    Actual (current code): ValidationError -> test FAILS, demonstrating H1.
    """
    from apps.account.utils import balance_utils
    from apps.account.utils.balance_utils import calculate_available_balance

    monkeypatch.setattr(balance_utils, "_get_current_pause_multiplier", lambda: 2)

    _, _, account = _account_with_vouchers(
        base_balance=Decimal("50.00"), num_vouchers=2, stored_multiplier=1
    )

    # Validation side — what the participant sees: 2 x $50 x live 2 = $200.
    assert calculate_available_balance(account) == Decimal("200")

    category = CategoryFactory(name="H1 Grocery")
    product = ProductFactory(
        category=category, price=Decimal("50.00"), quantity_in_stock=100
    )
    order = Order(account=account, status="pending")
    order.save()  # pending: full_clean runs the duplicate-guard only
    OrderItem.objects.create(order=order, product=product, quantity=3)  # $150
    assert order.total_price() == Decimal("150.00")

    # Confirming a $150 order against a $200 validated balance must work.
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


def test_m5b_key_changes_across_minute_boundary(monkeypatch):
    """M5b — the flip side: a true double-submit across a minute boundary is
    NOT detected.

    generate_idempotency_key embeds '%Y-%m-%d %H:%M', so submitting at
    10:00:59 and again at 10:01:01 yields different keys even though the
    300s TTL claims a 5-minute dedup window.

    Expected: the two keys are equal (same 5-minute window).
    Actual (current code): keys differ -> test FAILS, demonstrating M5.
    """
    import apps.orders.utils.order_services as order_services

    real_datetime = order_services.datetime

    class _FrozenDateTime(real_datetime):
        _now = None

        @classmethod
        def now(cls, tz=None):
            return cls._now

    cart = [{"product_id": 1, "quantity": 2}]
    frozen = _FrozenDateTime

    frozen._now = real_datetime(2026, 10, 16, 10, 0, 59)
    monkeypatch.setattr(order_services, "datetime", frozen)
    key_before = order_services.generate_idempotency_key(
        participant_id=4242, cart_items=cart
    )

    frozen._now = real_datetime(2026, 10, 16, 10, 1, 1)
    key_after = order_services.generate_idempotency_key(
        participant_id=4242, cart_items=cart
    )

    assert key_before == key_after


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
