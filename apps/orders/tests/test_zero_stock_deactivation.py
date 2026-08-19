"""
Regression/feature tests for Issue #97 ("Product deactivate") — confirming
an order that drains a product's stock to zero deactivates it immediately,
via Order._decrement_stock -> deactivate_out_of_stock_products.

Reactivation is deliberately out of scope: restocking (or an order
cancellation restoring stock) must never auto-reactivate a product —
that's always an explicit staff action. See apps/pantry/tests/
test_product_lifecycle.py for the utility-level coverage of that rule.
"""
from decimal import Decimal

import pytest

from apps.orders.tests.factories import (
    OrderFactory,
    OrderItemFactory,
    ParticipantFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.voucher.models import Voucher

pytestmark = pytest.mark.django_db


class TestZeroStockDeactivationOnConfirm:

    @pytest.fixture(autouse=True)
    def voucher_setting(self):
        return VoucherSettingFactory(active=True)

    def test_confirming_an_order_that_zeroes_stock_deactivates_the_product(self):
        participant = ParticipantFactory()
        account = participant.accountbalance
        Voucher.objects.filter(account=account).delete()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)

        product = ProductFactory(quantity_in_stock=3, active=True, price=Decimal('5.00'))
        order = OrderFactory(account=account, status='pending')
        OrderItemFactory(order=order, product=product, quantity=3)

        order.confirm()

        product.refresh_from_db()
        assert product.quantity_in_stock == 0
        assert product.active is False, (
            "A product whose stock is fully consumed by a confirmed order "
            "must be deactivated automatically."
        )

    def test_confirming_an_order_that_leaves_stock_does_not_deactivate(self):
        participant = ParticipantFactory()
        account = participant.accountbalance
        Voucher.objects.filter(account=account).delete()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)

        product = ProductFactory(quantity_in_stock=10, active=True, price=Decimal('5.00'))
        order = OrderFactory(account=account, status='pending')
        OrderItemFactory(order=order, product=product, quantity=3)

        order.confirm()

        product.refresh_from_db()
        assert product.quantity_in_stock == 7
        assert product.active is True

    def test_only_the_zeroed_product_is_deactivated_not_other_items_in_the_order(self):
        participant = ParticipantFactory()
        account = participant.accountbalance
        Voucher.objects.filter(account=account).delete()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)

        zeroed_product = ProductFactory(quantity_in_stock=2, active=True, price=Decimal('5.00'))
        surviving_product = ProductFactory(quantity_in_stock=50, active=True, price=Decimal('5.00'))
        order = OrderFactory(account=account, status='pending')
        OrderItemFactory(order=order, product=zeroed_product, quantity=2)
        OrderItemFactory(order=order, product=surviving_product, quantity=1)

        order.confirm()

        zeroed_product.refresh_from_db()
        surviving_product.refresh_from_db()
        assert zeroed_product.active is False
        assert surviving_product.active is True

    def test_cancelling_an_order_restores_stock_but_does_not_reactivate(self):
        """
        Restoring stock on cancel is a separate concern from reactivation —
        a product deactivated at zero stays deactivated until a staff
        member explicitly reactivates it.
        """
        participant = ParticipantFactory()
        account = participant.accountbalance
        Voucher.objects.filter(account=account).delete()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)

        product = ProductFactory(quantity_in_stock=3, active=True, price=Decimal('5.00'))
        order = OrderFactory(account=account, status='pending')
        OrderItemFactory(order=order, product=product, quantity=3)

        order.confirm()
        product.refresh_from_db()
        assert product.active is False

        # Mirrors OrderViewSet.cancel(): status flip + _restore_on_cancel()
        # in the same atomic block, exactly as the real cancel action does.
        order.status = 'cancelled'
        order._restore_on_cancel()
        order.save(update_fields=['status', 'updated_at'])

        product.refresh_from_db()
        assert product.quantity_in_stock == 3, "Stock must be restored on cancel"
        assert product.active is False, "Cancelling must not auto-reactivate the product"
