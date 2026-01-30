"""
Tests for Go Fresh order validation.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from apps.account.models import GoFreshSettings
from apps.pantry.tests.factories import (
    ParticipantFactory, VoucherFactory, CategoryFactory, 
    ProductFactory, VoucherSettingFactory
)
from apps.orders.tests.factories import OrderFactory, OrderItemFactory


@pytest.fixture(autouse=True)
def setup_voucher_settings():
    """Ensure VoucherSetting exists for all tests."""
    VoucherSettingFactory.create()


@pytest.mark.django_db
class TestGoFreshOrderValidation:
    """Test Go Fresh budget enforcement during order validation."""
    
    def test_within_go_fresh_limit_passes(self):
        """Order within Go Fresh budget should pass validation."""
        # Setup: 4-person household gets $20 Go Fresh budget
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=2, children=2)
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create Go Fresh category and product
        go_fresh_category = CategoryFactory(name="Go Fresh")
        product = ProductFactory(category=go_fresh_category, price=Decimal("5.00"))
        
        # Create order with $15 of Go Fresh items (within $20 budget)
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=3)  # 3 * $5 = $15
        
        # Should not raise ValidationError
        order.clean()
        
        # Should save go_fresh_total
        assert order.go_fresh_total == Decimal('15.00')
    
    def test_exceeding_go_fresh_limit_fails(self):
        """Order exceeding Go Fresh budget should fail validation."""
        # Setup: 2-person household gets $10 Go Fresh budget
        participant = ParticipantFactory(adults=2, children=0)
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create Go Fresh product at $8 each
        go_fresh_category = CategoryFactory(name="Go Fresh")
        product = ProductFactory(category=go_fresh_category, price=Decimal("8.00"))
        
        # Create order with $16 of Go Fresh items (exceeds $10 budget)
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=2)  # 2 * $8 = $16
        
        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        
        error_messages = str(exc_info.value)
        assert "Go Fresh balance exceeded" in error_messages
        assert "$16.00" in error_messages
        assert "$10.00" in error_messages
    
    def test_go_fresh_items_count_against_available_balance(self):
        """Go Fresh items should also count against overall available balance."""
        # Setup: Small balance so available balance is limited
        participant = ParticipantFactory(adults=1, children=0)  # 1 adult = ~$20 base
        account = participant.accountbalance
        # Don't set base_balance - let VoucherSetting determine it
        # With 1 adult and default setting ($20/adult), base is $20
        # available_balance is limited to 2 vouchers max, so max $40
        VoucherFactory(account=account, state='applied', multiplier=1)

        # Create Go Fresh and regular products
        go_fresh_category = CategoryFactory(name="Go Fresh")
        regular_category = CategoryFactory(name="Groceries")

        go_fresh_product = ProductFactory(category=go_fresh_category, price=Decimal("5.00"))
        regular_product = ProductFactory(category=regular_category, price=Decimal("50.00"))

        # Create order: $5 Go Fresh + $50 regular = $55 total (exceeds $20 available)
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=go_fresh_product, quantity=1)
        OrderItemFactory(order=order, product=regular_product, quantity=1)
        
        # Should fail on available balance even though Go Fresh item is within its budget
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        
        error_messages = str(exc_info.value)
        assert "Food balance exceeded" in error_messages or "balance exceeded" in error_messages.lower()
    
    def test_mixed_cart_validates_all_limits(self):
        """Mixed cart with Go Fresh, Hygiene, and regular items should validate all limits."""
        # Setup: Large household, large balance
        participant = ParticipantFactory(adults=3, children=3)
        account = participant.accountbalance
        account.base_balance = Decimal("300.00")  # Large balance to cover all items
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create categories and products
        go_fresh_category = CategoryFactory(name="Go Fresh")
        hygiene_category = CategoryFactory(name="Hygiene")
        regular_category = CategoryFactory(name="Pantry")
        
        go_fresh_product = ProductFactory(category=go_fresh_category, price=Decimal("10.00"))
        hygiene_product = ProductFactory(category=hygiene_category, price=Decimal("15.00"))
        regular_product = ProductFactory(category=regular_category, price=Decimal("20.00"))
        
        # Create order within all limits
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=go_fresh_product, quantity=2)  # $20 Go Fresh (within $25)
        OrderItemFactory(order=order, product=hygiene_product, quantity=2)  # $30 Hygiene
        OrderItemFactory(order=order, product=regular_product, quantity=2)  # $40 Regular
        
        # Should pass all validations
        order.clean()
        
        assert order.go_fresh_total == Decimal('20.00')
    
    def test_go_fresh_with_case_insensitive_category(self):
        """Go Fresh validation should be case-insensitive."""
        participant = ParticipantFactory(adults=2, children=0)
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create category with different casing
        go_fresh_category = CategoryFactory(name="go fresh")  # lowercase
        product = ProductFactory(category=go_fresh_category, price=Decimal("12.00"))
        
        # Create order exceeding $10 budget
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=1)

        # Should still enforce Go Fresh limit
        with pytest.raises(ValidationError) as exc_info:
            order.clean()
        
        assert "Go Fresh balance exceeded" in str(exc_info.value)
    
    def test_zero_go_fresh_items_doesnt_fail(self):
        """Order with no Go Fresh items should not fail Go Fresh validation."""
        participant = ParticipantFactory(adults=2, children=2)
        account = participant.accountbalance
        account.base_balance = Decimal("200.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create regular product only
        regular_category = CategoryFactory(name="Groceries")
        product = ProductFactory(category=regular_category, price=Decimal("30.00"))
        
        # Create order with only regular items
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=2)
        
        # Should pass validation
        order.clean()
        
        # go_fresh_total should be 0
        assert order.go_fresh_total == Decimal('0.00')
    
    def test_go_fresh_total_persists_after_validation(self):
        """go_fresh_total field should be set during validation."""
        participant = ParticipantFactory(adults=3, children=2)
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create Go Fresh product
        go_fresh_category = CategoryFactory(name="Go Fresh")
        product = ProductFactory(category=go_fresh_category, price=Decimal("7.50"))
        
        # Create order
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=2)  # $15.00
        
        # Run validation
        order.clean()
        
        # Check go_fresh_total is set
        assert order.go_fresh_total == Decimal('15.00')
        
        # Save and reload to verify persistence
        order.save()
        reloaded_order = type(order).objects.get(pk=order.pk)
        assert reloaded_order.go_fresh_total == Decimal('15.00')


@pytest.mark.django_db
class TestGoFreshEdgeCases:
    """Test edge cases for Go Fresh functionality."""
    
    def test_disabled_go_fresh_still_allows_orders(self):
        """When Go Fresh is disabled, orders should still process."""
        settings = GoFreshSettings.get_settings()
        settings.enabled = False
        settings.save()

        participant = ParticipantFactory(adults=2, children=2)
        account = participant.accountbalance
        account.base_balance = Decimal("200.00")  # Enough for available balance
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create Go Fresh product
        go_fresh_category = CategoryFactory(name="Go Fresh")
        product = ProductFactory(category=go_fresh_category, price=Decimal("50.00"))
        
        # Create order with expensive Go Fresh item
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=1)

        # Should not fail on Go Fresh limit (since disabled),
        # but may fail on available balance
        try:
            order.clean()
            # If it passes, go_fresh_total should still be calculated
            assert order.go_fresh_total == Decimal('50.00')
        except ValidationError as e:
            # If it fails, should be due to available balance, not Go Fresh
            assert "Go Fresh balance exceeded" not in str(e)

        # Re-enable
        settings.enabled = True
        settings.save()
    
    def test_product_without_category_doesnt_crash(self):
        """Product without category should not cause validation to crash."""
        participant = ParticipantFactory(adults=2, children=2)
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        VoucherFactory(account=account, state='applied', multiplier=1)
        
        # Create product without category
        product = ProductFactory(category=None, price=Decimal("10.00"))
        
        # Create order
        order = OrderFactory(account=account, status='confirmed')
        OrderItemFactory(order=order, product=product, quantity=1)

        # Should not crash
        order.clean()
        
        # Should have zero go_fresh_total
        assert order.go_fresh_total == Decimal('0.00')
