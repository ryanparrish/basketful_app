"""
Test to verify that orders exceeding available balance are rejected
BEFORE being created in the database.

This addresses the bug where orders were created despite validation failures.
"""
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from apps.orders.utils.order_validation import OrderValidation, OrderItemData
from apps.orders.models import Order
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
)


@pytest.mark.django_db
class TestBalanceValidationFix:
    """Test that balance validation prevents order creation."""

    def test_food_total_exceeds_available_balance_rejected_before_creation(self):
        """
        Test that when food items exceed available balance,
        validation fails BEFORE Order.objects.create() is called.
        """
        # Setup: Create voucher settings first
        VoucherSettingFactory.create()
        
        # Setup: Create user, participant, and account
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account_balance = participant.accountbalance

        # Create vouchers to provide $100 available balance
        # available_balance = base_balance * number_of_vouchers (up to limit=2)
        account_balance.base_balance = Decimal("50.00")
        account_balance.save()
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        
        # Verify available balance is $100 (2 vouchers * $50 base * 1 multiplier)
        available = account_balance.available_balance
        assert available == Decimal("100.00"), f"Expected $100, got ${available}"

        # Create food category and expensive product
        food_category = CategoryFactory(name="Food")
        expensive_product = ProductFactory(
            category=food_category,
            price=Decimal("150.00")  # Exceeds $100 balance
        )

        # Create order items that exceed balance
        items = [
            OrderItemData(
                product=expensive_product,
                quantity=1,
                delete=False
            )
        ]

        # Verify: OrderValidation should raise ValidationError
        validator = OrderValidation()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                items=items,
                participant=participant,
                account_balance=account_balance,
                user=user
            )

        # Check error message includes correct amounts
        error_msg = str(exc_info.value)
        assert "150.00" in error_msg
        assert "100.00" in error_msg
        assert "exceeds available voucher balance" in error_msg

        # CRITICAL: Verify NO Order was created in database
        order_count = Order.objects.filter(account=account_balance).count()
        assert order_count == 0, "Order should NOT be created when validation fails"

    def test_food_total_within_available_balance_passes(self):
        """
        Test that when food items are within available balance,
        validation passes successfully.
        """
        # Setup
        VoucherSettingFactory.create()
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account_balance = participant.accountbalance

        # Set available balance to $200 using vouchers
        # 2 vouchers * $100 base * 1 multiplier = $200
        account_balance.base_balance = Decimal("100.00")
        account_balance.save()
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)

        # Create food category and product within budget
        food_category = CategoryFactory(name="Food")
        affordable_product = ProductFactory(
            category=food_category,
            price=Decimal("100.00")  # Within $250 balance
        )

        # Create order items within balance
        items = [
            OrderItemData(
                product=affordable_product,
                quantity=2,  # Total: $200
                delete=False
            )
        ]

        # Verify: Should NOT raise ValidationError
        validator = OrderValidation()
        
        try:
            validator.validate_order_items(
                items=items,
                participant=participant,
                account_balance=account_balance,
                user=user
            )
        except ValidationError as e:
            pytest.fail(f"Validation should pass but raised: {e}")

    def test_go_fresh_exceeds_balance_rejected(self):
        """
        Test that Go Fresh items exceeding go_fresh_balance are rejected.
        """
        # Setup
        VoucherSettingFactory.create()
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account_balance = participant.accountbalance

        # Set balances including Go Fresh
        # Go Fresh balance is calculated from household size, typically $10 per adult
        account_balance.base_balance = Decimal("500.00")
        account_balance.save()
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        
        # Get the actual go_fresh_balance
        go_fresh_balance = account_balance.go_fresh_balance
        
        # Create Go Fresh category and expensive product that exceeds the balance
        go_fresh_category = CategoryFactory(name="Go Fresh")
        go_fresh_product = ProductFactory(
            category=go_fresh_category,
            price=go_fresh_balance + Decimal("1.00")  # Exceeds balance by $1
        )

        # Create order items
        items = [
            OrderItemData(
                product=go_fresh_product,
                quantity=1,
                delete=False
            )
        ]

        # Verify: Should raise ValidationError for Go Fresh
        validator = OrderValidation()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                items=items,
                participant=participant,
                account_balance=account_balance,
                user=user
            )

        error_msg = str(exc_info.value)
        assert "Go Fresh" in error_msg
        # Just verify that Go Fresh validation is working, amounts may vary

    def test_hygiene_exceeds_balance_still_caught(self):
        """
        Test that existing hygiene balance validation still works.
        """
        # Setup
        VoucherSettingFactory.create()
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account_balance = participant.accountbalance

        # Set balances with low hygiene balance
        # Hygiene balance is 1/3 of full_balance
        # To get $25 hygiene balance, we need $75 full balance
        # 2 vouchers * $37.50 base * 1 multiplier = $75
        account_balance.base_balance = Decimal("37.50")
        account_balance.save()
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account_balance, state='applied', voucher_type='grocery', multiplier=1)
        
        # Verify hygiene balance is $25 (1/3 of 75)
        hygiene = account_balance.hygiene_balance
        assert hygiene == Decimal("25.00"), f"Expected $25, got ${hygiene}"

        # Create hygiene category and expensive product
        hygiene_category = CategoryFactory(name="Hygiene")
        hygiene_product = ProductFactory(
            category=hygiene_category,
            price=Decimal("50.00")  # Exceeds $25 hygiene_balance
        )

        # Create order items
        items = [
            OrderItemData(
                product=hygiene_product,
                quantity=1,
                delete=False
            )
        ]

        # Verify: Should raise ValidationError for hygiene
        validator = OrderValidation()
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                items=items,
                participant=participant,
                account_balance=account_balance,
                user=user
            )

        error_msg = str(exc_info.value)
        assert "Hygiene" in error_msg or "hygiene" in error_msg
        assert "50.00" in error_msg
        assert "25.00" in error_msg


@pytest.mark.django_db
class TestCombinedBalanceValidation:
    """
    Regression tests for the combined food+hygiene balance check.

    Bug: validate_order_items checked food and hygiene totals separately
    against their individual limits, but never checked that their *combined*
    total stayed within the voucher pool.  An order with food=$132.50 and
    hygiene=$24.50 would pass both individual checks (food ≤ $135, hygiene
    ≤ $45) but fail later in _consume_vouchers() because the combined total
    $157 exceeded the $135 voucher balance.  This left a zombie PENDING order
    in the database and produced the "rejected → pending → accepted" pattern
    visible in the failure analytics dashboard.

    Fix: order_validation.py now checks food_total + hygiene_total ≤
    available_balance before any DB write, so the error is surfaced
    pre-creation and no orphan record is created.
    """

    def _setup_account(self, base_balance: Decimal):
        """
        Create a participant with exactly 2 applied grocery vouchers.

        available_balance = base_balance * 2
        hygiene_balance   = available_balance / 3
        """
        VoucherSettingFactory.create()
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account = participant.accountbalance
        account.base_balance = base_balance
        account.save()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
        return participant, account

    def test_combined_food_and_hygiene_exceeds_voucher_balance_rejected_before_creation(self):
        """
        Regression test: food + hygiene individually pass their limits but
        combined total exceeds available_balance → ValidationError raised
        BEFORE any Order record is written to the database.

        Mirrors the exact values from the production failure:
          base_balance = $67.50  →  available_balance = $135.00, hygiene_balance = $45.00
          food items   = $111.00  (< $135 individually ✓)
          hygiene      = $25.00   (< $45 individually  ✓)
          combined     = $136.00  (> $135              ✗  ← this was not caught before fix)
        """
        participant, account = self._setup_account(Decimal("67.50"))

        assert account.available_balance == Decimal("135.00"), (
            f"Expected $135.00, got {account.available_balance}"
        )
        assert account.hygiene_balance == Decimal("45.00"), (
            f"Expected $45.00, got {account.hygiene_balance}"
        )

        food_category = CategoryFactory(name="Food")
        hygiene_category = CategoryFactory(name="Hygiene")

        food_product = ProductFactory(category=food_category, price=Decimal("111.00"))
        hygiene_product = ProductFactory(category=hygiene_category, price=Decimal("25.00"))

        items = [
            OrderItemData(product=food_product, quantity=1),
            OrderItemData(product=hygiene_product, quantity=1),
        ]

        validator = OrderValidation()
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_order_items(
                items=items,
                participant=participant,
                account_balance=account,
            )

        error_msg = str(exc_info.value)
        assert "136.00" in error_msg
        assert "135.00" in error_msg

        # No order must have been created
        assert Order.objects.filter(account=account).count() == 0, (
            "No Order should exist when combined balance check fails"
        )

    def test_combined_food_and_hygiene_at_exact_balance_passes(self):
        """
        Boundary: food + hygiene exactly equals available_balance → should pass.
        """
        participant, account = self._setup_account(Decimal("67.50"))
        # available_balance = $135.00

        food_category = CategoryFactory(name="Food")
        hygiene_category = CategoryFactory(name="Hygiene")

        # $110 food + $25 hygiene = $135.00 exactly
        food_product = ProductFactory(category=food_category, price=Decimal("110.00"))
        hygiene_product = ProductFactory(category=hygiene_category, price=Decimal("25.00"))

        items = [
            OrderItemData(product=food_product, quantity=1),
            OrderItemData(product=hygiene_product, quantity=1),
        ]

        validator = OrderValidation()
        # Must not raise
        validator.validate_order_items(
            items=items,
            participant=participant,
            account_balance=account,
        )

    def test_combined_food_and_hygiene_within_balance_passes(self):
        """
        Happy path: food and hygiene both well within their limits → passes.
        """
        participant, account = self._setup_account(Decimal("67.50"))

        food_category = CategoryFactory(name="Food")
        hygiene_category = CategoryFactory(name="Hygiene")

        food_product = ProductFactory(category=food_category, price=Decimal("80.00"))
        hygiene_product = ProductFactory(category=hygiene_category, price=Decimal("20.00"))

        items = [
            OrderItemData(product=food_product, quantity=1),
            OrderItemData(product=hygiene_product, quantity=1),
        ]

        validator = OrderValidation()
        validator.validate_order_items(
            items=items,
            participant=participant,
            account_balance=account,
        )

    def test_create_order_rejects_combined_excess_without_creating_db_record(self):
        """
        Integration test: OrderOrchestration.create_order() must raise
        ValidationError and leave zero Order rows when the combined
        food+hygiene total would exceed available_balance.
        """
        from apps.orders.utils.order_utils import OrderOrchestration

        participant, account = self._setup_account(Decimal("67.50"))
        # available_balance = $135.00

        food_category = CategoryFactory(name="Food")
        hygiene_category = CategoryFactory(name="Hygiene")

        food_product = ProductFactory(
            category=food_category, price=Decimal("111.00"), quantity_in_stock=50
        )
        hygiene_product = ProductFactory(
            category=hygiene_category, price=Decimal("25.00"), quantity_in_stock=50
        )

        items = [
            OrderItemData(product=food_product, quantity=1),
            OrderItemData(product=hygiene_product, quantity=1),
        ]

        user = participant.user
        orchestrator = OrderOrchestration()

        with pytest.raises(ValidationError):
            orchestrator.create_order(
                account=account,
                order_items_data=items,
                user=user,
            )

        assert Order.objects.filter(account=account).count() == 0, (
            "create_order must not persist a pending order when combined balance check fails"
        )
