# apps/orders/tests/test_voucher_validation.py
"""Tests for voucher validation and consumption during order confirmation."""

import logging
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.orders.models import Order, OrderItem
from apps.orders.tests.factories import (
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    VoucherFactory,
)
from apps.voucher.models import Voucher, OrderVoucher

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestVoucherValidation:
    """Test voucher validation during order confirmation."""

    def test_order_exceeding_voucher_balance_raises_error(self):
        """
        Test that an order exceeding available voucher balance raises ValidationError.
        
        This test verifies the fix for the bug where orders could be $13 over voucher limit.
        """
        # Setup participant with limited vouchers
        participant = ParticipantFactory()
        participant.accountbalance.base_balance = Decimal("50.00")
        participant.accountbalance.save()
        
        # Create ONE voucher with $50 balance
        voucher = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        
        # Verify voucher amount
        assert voucher.voucher_amnt == Decimal("50.00")
        
        # Create expensive product
        category = CategoryFactory(name="Grocery")
        expensive_product = ProductFactory(
            name="Expensive Item",
            price=Decimal("63.00"),  # More than voucher balance
            category=category
        )
        
        # Create order
        order = Order.objects.create(
            account=participant.accountbalance,
            status="pending"
        )
        OrderItem.objects.create(
            order=order,
            product=expensive_product,
            quantity=1,
            price=expensive_product.price
        )
        
        # Verify order total exceeds voucher balance
        assert order.total_price() == Decimal("63.00")
        assert order.total_price() > voucher.voucher_amnt
        
        # Attempt to confirm order should raise ValidationError
        order.status = "confirmed"
        with pytest.raises(ValidationError) as exc_info:
            order.save()
        
        # Verify error message mentions exceeding balance
        error_msg = str(exc_info.value)
        # The error can be either "food balance exceeded" or "exceeds available voucher balance"
        # Both indicate the validation is working correctly
        assert ("food balance exceeded" in error_msg.lower() or 
                "exceeds available voucher balance" in error_msg.lower())
        assert "63.00" in error_msg
        assert "50.00" in error_msg
        
        logger.info("✓ Order exceeding voucher balance correctly rejected")

    def test_order_exceeding_two_vouchers_raises_error(self):
        """
        Test that an order exceeding TWO vouchers' combined balance raises ValidationError.
        """
        # Setup participant with two vouchers
        participant = ParticipantFactory()
        participant.accountbalance.base_balance = Decimal("50.00")
        participant.accountbalance.save()
        
        # Create TWO vouchers (max allowed)
        voucher1 = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        voucher2 = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        
        # Verify total voucher balance = $100
        total_voucher_balance = voucher1.voucher_amnt + voucher2.voucher_amnt
        assert total_voucher_balance == Decimal("100.00")
        
        # Create expensive product exceeding both vouchers
        category = CategoryFactory(name="Grocery")
        expensive_product = ProductFactory(
            name="Very Expensive Item",
            price=Decimal("113.00"),  # More than 2 vouchers
            category=category
        )
        
        # Create order
        order = Order.objects.create(
            account=participant.accountbalance,
            status="pending"
        )
        OrderItem.objects.create(
            order=order,
            product=expensive_product,
            quantity=1,
            price=expensive_product.price
        )
        
        # Verify order total exceeds combined voucher balance
        assert order.total_price() == Decimal("113.00")
        assert order.total_price() > total_voucher_balance
        
        # Attempt to confirm order should raise ValidationError
        order.status = "confirmed"
        with pytest.raises(ValidationError) as exc_info:
            order.save()
        
        # Verify error message
        error_msg = str(exc_info.value)
        # The error can be either "food balance exceeded" or "exceeds available voucher balance"
        # Both indicate the validation is working correctly
        assert ("food balance exceeded" in error_msg.lower() or 
                "exceeds available voucher balance" in error_msg.lower())
        
        logger.info("✓ Order exceeding two vouchers correctly rejected")

    def test_order_within_voucher_balance_succeeds(self):
        """
        Test that an order within voucher balance confirms successfully
        and creates OrderVoucher records.
        """
        # Setup participant with voucher
        participant = ParticipantFactory()
        participant.accountbalance.base_balance = Decimal("50.00")
        participant.accountbalance.save()
        
        voucher = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        
        # Create affordable product
        category = CategoryFactory(name="Grocery")
        product = ProductFactory(
            name="Affordable Item",
            price=Decimal("30.00"),
            category=category
        )
        
        # Create order
        order = Order.objects.create(
            account=participant.accountbalance,
            status="pending"
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.price
        )
        
        # Confirm order - should succeed
        order.status = "confirmed"
        order.save()
        
        # Verify voucher was consumed
        voucher.refresh_from_db()
        assert voucher.state == "consumed"
        assert voucher.active is False
        
        # Verify OrderVoucher record was created
        order_voucher = OrderVoucher.objects.filter(order=order, voucher=voucher).first()
        assert order_voucher is not None
        assert order_voucher.applied_amount == Decimal("30.00")
        
        # Verify notes were added to voucher
        assert f"Used on order {order.id}" in voucher.notes
        assert "$30.00" in voucher.notes
        
        logger.info("✓ Order within voucher balance succeeded and created logs")

    def test_order_consuming_two_vouchers_creates_two_records(self):
        """
        Test that an order requiring two vouchers creates two OrderVoucher records.
        """
        # Setup participant with two vouchers
        participant = ParticipantFactory()
        participant.accountbalance.base_balance = Decimal("50.00")
        participant.accountbalance.save()
        
        voucher1 = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        voucher2 = VoucherFactory.create(
            account=participant.accountbalance,
            voucher_type="grocery",
            state="applied",
            active=True
        )
        
        # Create product requiring both vouchers
        category = CategoryFactory(name="Grocery")
        product = ProductFactory(
            name="Large Order",
            price=Decimal("80.00"),  # Requires both vouchers
            category=category
        )
        
        # Create order
        order = Order.objects.create(
            account=participant.accountbalance,
            status="pending"
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.price
        )
        
        # Confirm order
        order.status = "confirmed"
        order.save()
        
        # Verify both vouchers were consumed
        voucher1.refresh_from_db()
        voucher2.refresh_from_db()
        assert voucher1.state == "consumed"
        assert voucher2.state == "consumed"
        assert voucher1.active is False
        assert voucher2.active is False
        
        # Verify TWO OrderVoucher records were created
        order_vouchers = OrderVoucher.objects.filter(order=order)
        assert order_vouchers.count() == 2
        
        # Verify applied amounts sum to order total
        total_applied = sum(ov.applied_amount for ov in order_vouchers)
        assert total_applied == Decimal("80.00")
        
        # Verify notes on both vouchers
        assert f"Used on order {order.id}" in voucher1.notes
        assert f"Used on order {order.id}" in voucher2.notes
        
        logger.info("✓ Order consuming two vouchers created two OrderVoucher records")

    def test_order_with_no_vouchers_raises_error(self):
        """Test that confirming an order with no vouchers raises ValidationError."""
        # Setup participant with NO vouchers
        participant = ParticipantFactory()
        participant.accountbalance.base_balance = Decimal("50.00")
        participant.accountbalance.save()
        
        # Verify no active vouchers (available_balance will be $0)
        active_vouchers = Voucher.objects.filter(
            account=participant.accountbalance,
            active=True,
            state="applied"
        )
        assert active_vouchers.count() == 0
        assert participant.accountbalance.available_balance == Decimal("0.00")
        
        # Create product
        category = CategoryFactory(name="Grocery")
        product = ProductFactory(name="Item", price=Decimal("20.00"), category=category)
        
        # Create order
        order = Order.objects.create(
            account=participant.accountbalance,
            status="pending"
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=product.price
        )
        
        # Attempt to confirm order - should raise ValidationError
        # because available_balance is $0 when there are no vouchers
        order.status = "confirmed"
        with pytest.raises(ValidationError) as exc_info:
            order.save()
        
        # Verify error indicates insufficient balance
        error_msg = str(exc_info.value)
        assert "food balance exceeded" in error_msg.lower()
        
        logger.info("✓ Order with no vouchers correctly rejected")
