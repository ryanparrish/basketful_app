"""
Regression tests: bulk_update_status must consume vouchers and decrement
stock on a genuine pending -> confirmed transition, exactly like the
single-order confirm() path does.

Root cause investigated for Issue #50 ("phantom double orders" — a
participant ended up with two independently-confirmed orders on the same
day). bulk_update_status moves status via a raw
Order.objects.filter(...).update(...) queryset call, which bypasses
Order.save() entirely — and _consume_vouchers()/_decrement_stock() are
only ever called from inside Order.save(). So an order confirmed via the
bulk "Command Palette" action (the default UI path whenever any orders
are checkbox-selected) never had its vouchers marked consumed or its
stock decremented. The participant's available_balance is computed from
`applied` vouchers, so it never dropped after a bulk-confirmed order,
letting further orders pass balance validation against funds that were
supposedly already spent.

This is distinct from (and more severe than) the confirmed/packing
duplicate-order guard bypass also found during investigation — that one
is closed by making a second pending order impossible in the first place
(see test_duplicate_order.py). This file guards the resource-consumption
side specifically, for whichever confirm mechanism staff use.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.orders.tests.factories import (
    OrderFactory,
    OrderItemFactory,
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.voucher.models import Voucher

BULK_URL = '/api/v1/orders/bulk_update_status/'


def _make_staff_client():
    user = UserFactory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestBulkConfirmConsumesResources:

    @pytest.fixture(autouse=True)
    def voucher_setting(self):
        return VoucherSettingFactory(active=True)

    def test_bulk_confirm_of_pending_order_consumes_voucher_and_decrements_stock(self):
        """
        The bug: confirming a pending order via bulk_update_status must have
        the exact same resource-consumption effect as Order.confirm() —
        it's a UI convenience for the same operation, not a different one.
        """
        participant = ParticipantFactory()
        account = participant.accountbalance
        # ParticipantFactory's post-creation signal auto-generates real
        # vouchers (per the "New participant -> generate vouchers" signal
        # chain) — clear those so this test's own voucher is the only
        # 'applied' one eligible for consumption, making the assertion
        # below deterministic.
        Voucher.objects.filter(account=account).delete()
        voucher = VoucherFactory(
            account=account, state='applied', voucher_type='grocery', multiplier=1
        )
        product = ProductFactory(quantity_in_stock=50)
        order = OrderFactory(account=account, status='pending')
        OrderItemFactory(order=order, product=product, quantity=3)

        client = _make_staff_client()
        response = client.post(
            BULK_URL, {'order_ids': [order.id], 'new_status': 'confirmed'}, format='json'
        )

        assert response.status_code == 200, response.data
        assert response.data['updated_count'] == 1

        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'confirmed'
        assert voucher.state == 'consumed', (
            "Voucher must be consumed when an order is confirmed via the bulk "
            "action, not left 'applied' forever."
        )
        assert product.quantity_in_stock == 47, (
            "Stock must be decremented by the ordered quantity when an order "
            "is confirmed via the bulk action."
        )

    def test_bulk_confirm_does_not_reconsume_on_already_confirmed_transitions(self):
        """
        Sanity check on the fix: transitions that don't represent a *first*
        confirmation (e.g. confirmed -> packing) must NOT re-trigger voucher
        consumption or stock decrement — those resources already moved.
        """
        participant = ParticipantFactory()
        account = participant.accountbalance
        voucher = VoucherFactory(
            account=account, state='consumed', voucher_type='grocery', multiplier=1
        )
        product = ProductFactory(quantity_in_stock=50)
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=3)

        client = _make_staff_client()
        response = client.post(
            BULK_URL, {'order_ids': [order.id], 'new_status': 'packing'}, format='json'
        )

        assert response.status_code == 200, response.data
        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'packing'
        assert voucher.state == 'consumed'  # unchanged
        assert product.quantity_in_stock == 50  # unchanged — not decremented again

    def test_bulk_confirm_multiple_pending_orders_each_consume_independently(self):
        """Bulk-confirming several pending orders at once must consume each one's own vouchers/stock."""
        participants = [ParticipantFactory() for _ in range(2)]
        orders = []
        products = []
        for p in participants:
            account = p.accountbalance
            VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
            product = ProductFactory(quantity_in_stock=20)
            order = OrderFactory(account=account, status='pending')
            OrderItemFactory(order=order, product=product, quantity=2)
            orders.append(order)
            products.append(product)

        client = _make_staff_client()
        response = client.post(
            BULK_URL,
            {'order_ids': [o.id for o in orders], 'new_status': 'confirmed'},
            format='json',
        )

        assert response.status_code == 200, response.data
        assert response.data['updated_count'] == 2

        for order, product, participant in zip(orders, products, participants):
            order.refresh_from_db()
            product.refresh_from_db()
            assert order.status == 'confirmed'
            assert product.quantity_in_stock == 18
            assert Voucher.objects.filter(
                account=participant.accountbalance, state='consumed'
            ).exists()
