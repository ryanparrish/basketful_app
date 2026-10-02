"""
Regression coverage for a fixed production incident: cancelling an
already-confirmed/paid Order — through any real path (bulk action, the
single-order `cancel` action, or a plain PATCH) — must restore its
consumed voucher and decremented stock, and must leave an audit trail.

This is the mirror-image of the bug fixed in
test_bulk_confirm_consumes_resources.py (Issue #50) — that fix routes a
genuine pending -> confirmed transition through Order.confirm()
individually so resources are consumed correctly. The same discipline now
applies to cancellation: Order.save() (apps/orders/models.py) restores
vouchers/stock via _restore_on_cancel() whenever a transition INTO
'cancelled' comes FROM a resource-holding status (Order.RESOURCE_HOLDING_
STATUSES = {'confirmed', 'packing', 'completed'}), and bulk_update_status
(apps/orders/api/views.py) routes a genuine cancellation through an
individual save() call instead of the raw queryset.update() that used to
bypass it entirely.

Every status transition, through every path, now also writes an
OrderValidationLog row (INFO level for ordinary transitions, WARNING for
bypass corrections, as before) with the acting user attached wherever the
request had one. This closes the gap that made a real production
cancellation (order #1087) impossible to trace after the fact: staff and
the participant both denied cancelling it, and checking OrderValidationLog
for a bypass didn't rule anything out, because ordinary (non-bypass)
transitions used to write nothing at all, through any path.
"""
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.log.models import OrderValidationLog
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
from apps.voucher.models import OrderVoucher, Voucher

BULK_URL = '/api/v1/orders/bulk_update_status/'


def _single_cancel_url(order_id):
    return f'/api/v1/orders/{order_id}/cancel/'


def _order_url(order_id):
    return f'/api/v1/orders/{order_id}/'


def _make_staff_client():
    user = UserFactory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestBulkCancelRestoresVouchers:

    @pytest.fixture(autouse=True)
    def voucher_setting(self):
        return VoucherSettingFactory(active=True)

    def _make_order_with_consumed_voucher(self, status='confirmed'):
        """An order whose voucher was consumed and stock decremented at
        confirmation time — i.e. what order #1087 looked like right before
        it was cancelled. `status` lets callers simulate a later stage
        (e.g. 'packing') without re-consuming resources."""
        participant = ParticipantFactory()
        account = participant.accountbalance
        # ParticipantFactory's signal chain auto-generates real vouchers —
        # clear those so the single voucher below is unambiguous.
        Voucher.objects.filter(account=account).delete()
        voucher = VoucherFactory(
            account=account, state='consumed', voucher_type='grocery', multiplier=1
        )
        # Product started at 50; 3 were already decremented at confirmation.
        product = ProductFactory(quantity_in_stock=47)
        order = OrderFactory(account=account, status=status, paid=True)
        OrderItemFactory(order=order, product=product, quantity=3)
        # _restore_on_cancel() finds vouchers to restore via the OrderVoucher
        # join table (apps/orders/models.py), not by scanning for any
        # consumed voucher on the account — real confirmation always creates
        # this row. Without it, _restore_on_cancel would find nothing to
        # restore regardless of which code path ran, which would make every
        # test below pass for the wrong reason.
        OrderVoucher.objects.create(order=order, voucher=voucher, applied_amount=Decimal('39.75'))
        return order, voucher, product

    def test_bulk_cancel_of_confirmed_order_restores_voucher_and_stock(self):
        """Matches production order #1087: bulk-cancelling a confirmed order
        must return the voucher to 'applied' and restore stock."""
        order, voucher, product = self._make_order_with_consumed_voucher()

        client = _make_staff_client()
        response = client.post(
            BULK_URL, {'order_ids': [order.id], 'new_status': 'cancelled'}, format='json'
        )

        assert response.status_code == 200, response.data
        assert response.data['updated_count'] == 1

        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'cancelled'
        assert voucher.state == 'applied', (
            "Bulk-cancelling a confirmed order must restore its voucher, "
            "same as the single-order `cancel` action."
        )
        assert product.quantity_in_stock == 50, (
            "Bulk-cancelling a confirmed order must restore the stock it decremented."
        )

    def test_bulk_cancel_of_packing_order_restores_voucher_and_stock(self):
        """A 'packing' order also has consumed vouchers/decremented stock —
        confirmation is the only point those are consumed, so cancelling
        from packing (not just confirmed) must restore them too."""
        order, voucher, product = self._make_order_with_consumed_voucher(status='packing')

        client = _make_staff_client()
        response = client.post(
            BULK_URL, {'order_ids': [order.id], 'new_status': 'cancelled'}, format='json'
        )

        assert response.status_code == 200, response.data
        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'cancelled'
        assert voucher.state == 'applied'
        assert product.quantity_in_stock == 50

    def test_bulk_cancel_of_confirmed_order_writes_audit_trail(self):
        """An ordinary (non-bypass) bulk cancel must leave a record of who
        cancelled the order and when — this is exactly what was missing
        when investigating order #1087."""
        order, _voucher, _product = self._make_order_with_consumed_voucher()

        client = _make_staff_client()
        response = client.post(
            BULK_URL, {'order_ids': [order.id], 'new_status': 'cancelled'}, format='json'
        )

        assert response.status_code == 200, response.data
        order.refresh_from_db()
        assert order.status == 'cancelled'

        logs = OrderValidationLog.objects.filter(order=order)
        assert logs.count() == 1, (
            "An ordinary bulk cancel must write exactly one audit row — "
            "previously this wrote zero, bypass or not."
        )
        log = logs.first()
        assert log.log_type == OrderValidationLog.INFO
        assert 'confirmed' in log.message and 'cancelled' in log.message

    def test_single_order_cancel_action_does_restore_voucher_and_stock(self):
        """Control: the dedicated single-order `cancel` action, given the
        exact same fixture as the bulk tests above, restores the voucher
        and stock — confirming Order.save()'s new restore branch doesn't
        double-restore now that the action's own manual call was removed."""
        order, voucher, product = self._make_order_with_consumed_voucher()

        client = _make_staff_client()
        response = client.post(_single_cancel_url(order.id))

        assert response.status_code == 200, response.data

        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'cancelled'
        assert voucher.state == 'applied', (
            "The single-order cancel action is expected to restore the "
            "voucher via _restore_on_cancel() — if this fails, the control "
            "itself is broken, not just the bulk path."
        )
        assert product.quantity_in_stock == 50, (
            "The single-order cancel action is expected to restore stock, "
            "exactly once (not double-restored now that Order.save() also "
            "triggers _restore_on_cancel())."
        )

    def test_generic_patch_cancel_restores_voucher_and_writes_audit_trail(self):
        """The real path the "Cancel Order" button and status dropdown use
        (plain PATCH /orders/{id}/, not the dedicated /cancel/ action or
        bulk_update_status) — zero existing coverage before this fix, and
        the most likely path order #1087 actually went through."""
        order, voucher, product = self._make_order_with_consumed_voucher()
        client = _make_staff_client()

        response = client.patch(
            _order_url(order.id), {'status': 'cancelled'}, format='json'
        )

        assert response.status_code == 200, response.data
        order.refresh_from_db()
        voucher.refresh_from_db()
        product.refresh_from_db()

        assert order.status == 'cancelled'
        assert voucher.state == 'applied'
        assert product.quantity_in_stock == 50

        logs = OrderValidationLog.objects.filter(order=order)
        assert logs.count() == 1
        log = logs.first()
        assert log.user_id is not None, (
            "A generic PATCH status change must attribute a user — this is "
            "exactly the 'no fingerprint of any kind' gap found investigating #1087."
        )
