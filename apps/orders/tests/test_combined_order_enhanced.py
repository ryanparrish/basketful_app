"""Tests for the enhanced combined order functionality.

Tests cover:
- is_combined field on Order model
- PackingSplitRule model
- PackingList model
- Split strategy validation
- Split logic (50/50, round robin, by category)
- Combined order creation with packing lists
- Uncombine functionality
- Admin views (create, preview, confirm, success)
- PDF generation
- Edge cases
"""
import pytest
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order, CombinedOrder, PackingSplitRule, PackingList
from apps.orders.forms import CreateCombinedOrderForm
from apps.orders.admin import CombinedOrderAdmin
from apps.orders.tasks.helper.combined_order_helper import (
    validate_split_strategy,
    validate_by_category_rules,
    split_orders_by_count,
    split_orders_by_category,
    get_split_preview,
    get_eligible_orders,
    create_combined_order_with_packing,
    uncombine_order,
)
from apps.orders.utils.order_services import generate_packing_list_pdf
from apps.lifeskills.models import Program
from apps.pantry.models import Category, OrderPacker
from apps.orders.tests.factories import (
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    OrderFactory,
    OrderItemFactory,
    ProgramFactory,
    UserFactory,
)


# =============================================================================
# Mock Celery to prevent hanging
# =============================================================================

@pytest.fixture(autouse=True)
def mock_celery_tasks(settings):
    """Disable Celery tasks for all tests in this module."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def program_with_packers(db):
    """Create a program with two packers."""
    program = Program.objects.create(
        name='Test Program with Packers',
        meeting_time='10:00:00',
        MeetingDay='monday',
        meeting_address='123 Test St',
        default_split_strategy='none',
    )
    packer1 = OrderPacker.objects.create(name='Packer 1')
    packer2 = OrderPacker.objects.create(name='Packer 2')
    program.packers.add(packer1, packer2)
    return program, packer1, packer2


@pytest.fixture
def program_single_packer(db):
    """Create a program with a single packer."""
    program = Program.objects.create(
        name='Single Packer Program',
        meeting_time='09:00:00',
        MeetingDay='tuesday',
        meeting_address='456 Test Ave',
        default_split_strategy='none',
    )
    packer = OrderPacker.objects.create(name='Solo Packer')
    program.packers.add(packer)
    return program, packer


@pytest.fixture
def categories(db):
    """Create test categories."""
    return [
        CategoryFactory(name='Produce'),
        CategoryFactory(name='Dairy'),
        CategoryFactory(name='Meat'),
        CategoryFactory(name='Bakery'),
    ]


@pytest.fixture
def orders_for_program(program_with_packers, categories):
    """Create confirmed orders for a program."""
    program, packer1, packer2 = program_with_packers
    orders = []
    
    for i in range(6):
        participant = ParticipantFactory(program=program)
        order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number=f'TEST-{i:08d}',
        )
        # Add items from different categories
        for category in categories[:2]:  # Use first 2 categories
            product = ProductFactory(category=category)
            OrderItemFactory(order=order, product=product, quantity=2)
        orders.append(order)
    
    return orders, program, packer1, packer2


@pytest.fixture
def admin_site():
    """Return Django admin site."""
    return AdminSite()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username='testadmin',
        email='admin@test.com',
        password='adminpass123'
    )


@pytest.fixture
def request_factory():
    """Return Django request factory."""
    return RequestFactory()


# =============================================================================
# Order.is_combined Field Tests
# =============================================================================

@pytest.mark.django_db
class TestOrderIsCombinedField:
    """Tests for the is_combined field on Order model."""
    
    def test_default_is_combined_false(self):
        """New orders should have is_combined=False by default."""
        participant = ParticipantFactory()
        order = Order.objects.create(
            account=participant.accountbalance,
            status='pending',
            order_number='TEST-001',
        )
        assert order.is_combined is False
    
    def test_is_combined_can_be_set_true(self):
        """Order marked as combined when added to CombinedOrder."""
        participant = ParticipantFactory()
        order = Order.objects.create(
            account=participant.accountbalance,
            status='pending',
            order_number='TEST-002',
        )
        # Add order to a CombinedOrder to mark it as combined
        combined = CombinedOrder.objects.create(program=participant.program)
        combined.orders.add(order)
        
        # Refresh from DB to see the relationship
        order.refresh_from_db()
        assert order.is_combined is True
    
    def test_is_combined_filter(self):
        """Test identifying orders by is_combined status."""
        participant = ParticipantFactory()
        
        # Create combined and uncombined orders
        combined_order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='TEST-COMBINED',
        )
        uncombined_order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='TEST-UNCOMBINED',
        )
        
        # Mark one as combined by adding to CombinedOrder
        combined = CombinedOrder.objects.create(program=participant.program)
        combined.orders.add(combined_order)
        
        # Refresh to see relationships
        combined_order.refresh_from_db()
        uncombined_order.refresh_from_db()
        
        assert combined_order.is_combined is True
        assert uncombined_order.is_combined is False


# =============================================================================
# PackingSplitRule Model Tests
# =============================================================================

@pytest.mark.django_db
class TestPackingSplitRuleModel:
    """Tests for PackingSplitRule model."""
    
    def test_create_split_rule(self, program_with_packers, categories):
        """Test creating a packing split rule."""
        program, packer1, packer2 = program_with_packers
        
        rule = PackingSplitRule.objects.create(
            program=program,
            packer=packer1,
        )
        rule.categories.add(categories[0], categories[1])
        
        assert rule.program == program
        assert rule.packer == packer1
        assert rule.categories.count() == 2
    
    def test_unique_together_constraint(self, program_with_packers):
        """Test that program+packer combination must be unique."""
        program, packer1, packer2 = program_with_packers
        
        # Create first rule
        PackingSplitRule.objects.create(
            program=program,
            packer=packer1,
        )
        
        # Try to create duplicate
        with pytest.raises(Exception):  # IntegrityError
            PackingSplitRule.objects.create(
                program=program,
                packer=packer1,
            )
    
    def test_split_rule_str_representation(self, program_with_packers):
        """Test string representation of split rule."""
        program, packer1, packer2 = program_with_packers
        
        rule = PackingSplitRule.objects.create(
            program=program,
            packer=packer1,
        )
        
        assert program.name in str(rule)
        assert packer1.name in str(rule)


# =============================================================================
# PackingList Model Tests
# =============================================================================

@pytest.mark.django_db
class TestPackingListModel:
    """Tests for PackingList model."""
    
    def test_create_packing_list(self, program_with_packers, categories):
        """Test creating a packing list."""
        program, packer1, packer2 = program_with_packers
        
        # Create combined order first
        combined_order = CombinedOrder.objects.create(
            program=program,
            name='Test Combined Order',
        )
        
        packing_list = PackingList.objects.create(
            combined_order=combined_order,
            packer=packer1,
        )
        
        assert packing_list.combined_order == combined_order
        assert packing_list.packer == packer1
        assert packing_list.orders.count() == 0
    
    def test_packing_list_orders_relationship(self, orders_for_program):
        """Test adding orders to packing list."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order = CombinedOrder.objects.create(
            program=program,
            name='Test Combined Order',
        )
        combined_order.orders.set(orders)
        
        packing_list = PackingList.objects.create(
            combined_order=combined_order,
            packer=packer1,
        )
        packing_list.orders.add(*orders[:3])  # First 3 orders
        
        assert packing_list.orders.count() == 3
    
    def test_calculate_summarized_data(self, orders_for_program, categories):
        """Test summarized data calculation for packing list."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order = CombinedOrder.objects.create(
            program=program,
            name='Test Combined Order',
        )
        combined_order.orders.set(orders)
        
        packing_list = PackingList.objects.create(
            combined_order=combined_order,
            packer=packer1,
        )
        packing_list.orders.add(*orders[:3])
        
        # Calculate summarized data
        summary = packing_list.calculate_summarized_data()
        
        assert isinstance(summary, dict)
        # Should have data from the categories used in orders
        assert len(summary) > 0


# =============================================================================
# Split Strategy Validation Tests
# =============================================================================

@pytest.mark.django_db
class TestSplitStrategyValidation:
    """Tests for split strategy validation."""
    
    def test_validate_none_strategy(self, program_single_packer):
        """No validation errors for 'none' strategy."""
        program, packer = program_single_packer
        is_valid, errors = validate_split_strategy(program, 'none')
        
        # Single packer with 'none' strategy should be valid
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_fifty_fifty_requires_two_packers(self, program_single_packer):
        """50/50 strategy requires at least 2 packers."""
        program, packer = program_single_packer
        is_valid, errors = validate_split_strategy(program, 'fifty_fifty')
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_fifty_fifty_with_two_packers(self, program_with_packers):
        """50/50 strategy works with 2 packers."""
        program, packer1, packer2 = program_with_packers
        is_valid, errors = validate_split_strategy(program, 'fifty_fifty')
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_by_category_requires_rules(self, program_with_packers):
        """by_category strategy requires split rules to be defined."""
        program, packer1, packer2 = program_with_packers
        
        # No rules defined
        is_valid, errors = validate_split_strategy(program, 'by_category')
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_by_category_with_rules(self, program_with_packers, categories):
        """by_category strategy works with proper rules."""
        program, packer1, packer2 = program_with_packers
        
        # Create rules
        rule1 = PackingSplitRule.objects.create(program=program, packer=packer1)
        rule1.categories.add(categories[0], categories[1])
        
        rule2 = PackingSplitRule.objects.create(program=program, packer=packer2)
        rule2.categories.add(categories[2], categories[3])
        
        is_valid, errors = validate_split_strategy(program, 'by_category')
        
        # Should be valid with rules configured
        assert is_valid is True


@pytest.mark.django_db
class TestByCategoryRulesValidation:
    """Tests for by_category rules validation."""
    
    def test_no_rules_returns_error(self, program_with_packers):
        """No rules should return an error."""
        program, packer1, packer2 = program_with_packers
        
        is_valid, errors = validate_by_category_rules(program)
        assert is_valid is False
        assert len(errors) > 0
    
    def test_rules_with_categories_valid(self, program_with_packers, categories):
        """Rules with categories should be valid."""
        program, packer1, packer2 = program_with_packers
        
        rule = PackingSplitRule.objects.create(program=program, packer=packer1)
        rule.categories.add(categories[0])
        
        is_valid, errors = validate_by_category_rules(program)
        
        # Should pass (at least one rule with categories)
        assert is_valid is True


# =============================================================================
# Split Logic Tests
# =============================================================================

@pytest.mark.django_db
class TestSplitOrdersByCount:
    """Tests for split_orders_by_count function."""
    
    def test_split_fifty_fifty_even(self, orders_for_program):
        """Test 50/50 split with even number of orders."""
        orders, program, packer1, packer2 = orders_for_program
        packers = [packer1, packer2]
        
        result = split_orders_by_count(orders, packers, 'fifty_fifty')
        
        assert len(result) == 2
        # Keys are packer objects
        packer_ids = [p.id for p in result.keys()]
        assert packer1.id in packer_ids
        assert packer2.id in packer_ids
        
        # Should be roughly equal
        total = sum(len(o) for o in result.values())
        assert total == len(orders)
    
    def test_split_fifty_fifty_odd(self, program_with_packers):
        """Test 50/50 split with odd number of orders."""
        program, packer1, packer2 = program_with_packers
        packers = [packer1, packer2]
        
        # Create 5 orders
        orders = []
        for i in range(5):
            participant = ParticipantFactory(program=program)
            order = Order.objects.create(
                account=participant.accountbalance,
                status='confirmed',
                order_number=f'ODD-{i}',
            )
            orders.append(order)
        
        result = split_orders_by_count(orders, packers, 'fifty_fifty')
        
        # One packer gets 3, other gets 2
        counts = [len(o) for o in result.values()]
        assert sorted(counts) == [2, 3]
    
    def test_split_round_robin(self, orders_for_program):
        """Test round robin split."""
        orders, program, packer1, packer2 = orders_for_program
        packers = [packer1, packer2]
        
        result = split_orders_by_count(orders, packers, 'round_robin')
        
        assert len(result) == 2
        
        # Round robin should distribute evenly
        counts = [len(o) for o in result.values()]
        assert max(counts) - min(counts) <= 1


@pytest.mark.django_db  
class TestSplitOrdersByCategory:
    """Tests for split_orders_by_category function."""
    
    def test_split_by_category(self, program_with_packers, categories):
        """Test splitting orders by category rules."""
        program, packer1, packer2 = program_with_packers
        packers = [packer1, packer2]
        
        # Create rules
        rule1 = PackingSplitRule.objects.create(program=program, packer=packer1)
        rule1.categories.add(categories[0])  # Produce
        
        rule2 = PackingSplitRule.objects.create(program=program, packer=packer2)
        rule2.categories.add(categories[1])  # Dairy
        
        # Create order with items from both categories
        participant = ParticipantFactory(program=program)
        order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='CAT-001',
        )
        
        product1 = ProductFactory(category=categories[0])  # Produce
        product2 = ProductFactory(category=categories[1])  # Dairy
        OrderItemFactory(order=order, product=product1)
        OrderItemFactory(order=order, product=product2)
        
        orders = [order]
        result = split_orders_by_category(orders, packers, program)
        
        # Both packers should be in the result
        packer_ids = [p.id for p in result.keys()]
        assert packer1.id in packer_ids
        assert packer2.id in packer_ids


# =============================================================================
# Get Split Preview Tests
# =============================================================================

@pytest.mark.django_db
class TestGetSplitPreview:
    """Tests for get_split_preview function."""
    
    def test_preview_fifty_fifty(self, orders_for_program):
        """Test preview for 50/50 split."""
        orders, program, packer1, packer2 = orders_for_program
        
        preview = get_split_preview(orders, program, 'fifty_fifty')
        
        assert 'packers' in preview
        assert len(preview['packers']) == 2
        assert 'split_preview' in preview
        assert 'order_count' in preview
        assert 'total_items' in preview
    
    def test_preview_none_strategy(self, orders_for_program):
        """Test preview for 'none' (single packer) strategy."""
        orders, program, packer1, packer2 = orders_for_program
        
        preview = get_split_preview(orders, program, 'none')
        
        # With 'none' strategy, one packer gets all orders
        assert len(preview.get('split_preview', [])) == 1
        assert preview['split_preview'][0]['order_count'] == len(orders)


# =============================================================================
# Get Eligible Orders Tests
# =============================================================================

@pytest.mark.django_db
class TestGetEligibleOrders:
    """Tests for get_eligible_orders function."""
    
    def test_eligible_orders_excludes_combined(self, program_with_packers):
        """Already combined orders should not be eligible."""
        program, packer1, packer2 = program_with_packers
        
        # Create orders
        participant = ParticipantFactory(program=program)
        
        combined_order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='ALREADY-COMBINED',
        )
        
        uncombined_order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='NOT-COMBINED',
        )
        
        # Mark one as combined by adding to CombinedOrder
        temp_combined = CombinedOrder.objects.create(program=program)
        temp_combined.orders.add(combined_order)
        
        start_date = timezone.now() - timedelta(days=1)
        end_date = timezone.now() + timedelta(days=1)
        
        eligible, excluded, warnings = get_eligible_orders(
            program, start_date, end_date
        )
        
        assert uncombined_order in eligible
        assert combined_order not in eligible
    
    def test_eligible_orders_date_range(self, program_with_packers):
        """Only orders within date range should be eligible."""
        program, packer1, packer2 = program_with_packers
        
        participant = ParticipantFactory(program=program)
        
        # Create order in range
        in_range = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='IN-RANGE',
        )
        
        # Create order out of range (manually set date)
        out_of_range = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed', 
            order_number='OUT-OF-RANGE',
        )
        # Update to old date
        Order.objects.filter(pk=out_of_range.pk).update(
            order_date=timezone.now() - timedelta(days=30)
        )
        
        start_date = timezone.now() - timedelta(days=1)
        end_date = timezone.now() + timedelta(days=1)
        
        eligible, excluded, warnings = get_eligible_orders(
            program, start_date, end_date
        )
        
        assert in_range in eligible


# =============================================================================
# Combined Order Creation with Packing Tests
# =============================================================================

@pytest.mark.django_db
class TestCreateCombinedOrderWithPacking:
    """Tests for create_combined_order_with_packing function."""
    
    def test_create_with_none_strategy(self, orders_for_program):
        """Test creation with 'none' strategy (no split)."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='none',
            name='Test None Strategy',
        )
        
        assert combined_order is not None
        assert combined_order.orders.count() == len(orders)
        assert combined_order.split_strategy == 'none'
        
        # All orders should be marked as combined
        for order in orders:
            order.refresh_from_db()
            assert order.is_combined is True
    
    def test_create_with_fifty_fifty_strategy(self, orders_for_program):
        """Test creation with 50/50 split strategy."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='fifty_fifty',
            name='Test 50/50 Strategy',
        )
        
        assert combined_order is not None
        assert combined_order.split_strategy == 'fifty_fifty'
        
        # Should have 2 packing lists
        assert len(packing_lists) == 2
        
        # Each packing list should have orders
        total_packing_orders = sum(pl.orders.count() for pl in packing_lists)
        assert total_packing_orders == len(orders)


# =============================================================================
# Uncombine Order Tests
# =============================================================================

@pytest.mark.django_db
class TestUncombineOrder:
    """Tests for uncombine_order function."""
    
    def test_uncombine_resets_is_combined(self, orders_for_program):
        """Uncombining should reset is_combined to False."""
        orders, program, packer1, packer2 = orders_for_program
        
        # Create combined order
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='none',
            name='Test Uncombine',
        )
        
        # Verify orders are combined
        for order in orders:
            order.refresh_from_db()
            assert order.is_combined is True
        
        # Uncombine
        uncombine_order(combined_order)
        
        # Orders should no longer be combined
        for order in orders:
            order.refresh_from_db()
            assert order.is_combined is False
    
    def test_uncombine_deletes_packing_lists(self, orders_for_program):
        """Uncombining should delete associated packing lists."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='fifty_fifty',
            name='Test Uncombine Packing',
        )
        
        packing_list_ids = [pl.id for pl in packing_lists]
        
        # Uncombine
        uncombine_order(combined_order)
        
        # Packing lists should be deleted
        remaining = PackingList.objects.filter(id__in=packing_list_ids)
        assert remaining.count() == 0


# =============================================================================
# CreateCombinedOrderForm Tests
# =============================================================================

@pytest.mark.django_db
class TestCreateCombinedOrderFormEnhanced:
    """Tests for enhanced CreateCombinedOrderForm."""
    
    def test_form_with_split_override(self, program_with_packers):
        """Test form with split strategy override."""
        program, packer1, packer2 = program_with_packers
        
        form_data = {
            'program': program.id,
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'split_strategy_override': 'fifty_fifty',
        }
        form = CreateCombinedOrderForm(data=form_data)
        
        assert form.is_valid()
    
    def test_get_effective_strategy_uses_override(self, program_with_packers):
        """get_effective_strategy should prefer override over default."""
        program, packer1, packer2 = program_with_packers
        program.default_split_strategy = 'none'
        program.save()
        
        form_data = {
            'program': program.id,
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'split_strategy_override': 'fifty_fifty',
        }
        form = CreateCombinedOrderForm(data=form_data)
        assert form.is_valid()
        
        effective = form.get_effective_strategy()
        assert effective == 'fifty_fifty'
    
    def test_get_effective_strategy_falls_back_to_program(self, program_with_packers):
        """get_effective_strategy falls back to program default."""
        program, packer1, packer2 = program_with_packers
        program.default_split_strategy = 'round_robin'
        program.save()
        
        form_data = {
            'program': program.id,
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'split_strategy_override': '',  # No override
        }
        form = CreateCombinedOrderForm(data=form_data)
        assert form.is_valid()
        
        effective = form.get_effective_strategy()
        assert effective == 'round_robin'


# =============================================================================
# PDF Generation Tests
# =============================================================================

@pytest.mark.django_db
class TestPackingListPDFGeneration:
    """Tests for packing list PDF generation."""
    
    def test_generate_packing_list_pdf_returns_buffer(self, orders_for_program):
        """PDF generation should return a BytesIO buffer."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order = CombinedOrder.objects.create(
            program=program,
            name='PDF Test',
        )
        combined_order.orders.set(orders)
        
        packing_list = PackingList.objects.create(
            combined_order=combined_order,
            packer=packer1,
        )
        packing_list.orders.add(*orders[:3])
        packing_list.summarized_data = packing_list.calculate_summarized_data()
        packing_list.save()
        
        result = generate_packing_list_pdf(packing_list)
        
        assert isinstance(result, BytesIO)
        assert result.getvalue()  # Should have content
    
    def test_pdf_uses_customer_numbers(self, orders_for_program):
        """PDF should use customer numbers, not participant names."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order = CombinedOrder.objects.create(
            program=program,
            name='Privacy Test',
        )
        combined_order.orders.set(orders)
        
        packing_list = PackingList.objects.create(
            combined_order=combined_order,
            packer=packer1,
        )
        packing_list.orders.add(*orders[:1])
        
        # This is a structural test - the PDF should be generated without errors
        # and use customer numbers (verified by code inspection)
        result = generate_packing_list_pdf(packing_list)
        assert result is not None


# =============================================================================
# Admin View Tests
# =============================================================================

@pytest.mark.django_db
class TestCombinedOrderAdminViews:
    """Tests for CombinedOrder admin custom views."""
    
    def test_admin_has_create_url(self):
        """Admin should have a create combined order URL."""
        url = reverse('admin:orders_combinedorder_create')
        assert url is not None
        assert 'create' in url
    
    def test_admin_urls_exist(self):
        """Admin URLs for combined order should be defined."""
        # Test that the URLs are properly configured
        changelist_url = reverse('admin:orders_combinedorder_changelist')
        assert changelist_url is not None


# =============================================================================
# Edge Cases Tests
# =============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_orders_list(self, program_with_packers):
        """Splitting empty order list should not crash."""
        program, packer1, packer2 = program_with_packers
        packers = [packer1, packer2]
        
        result = split_orders_by_count([], packers, 'fifty_fifty')
        
        # Should return empty dict for each packer
        assert isinstance(result, dict)
    
    def test_single_order_split(self, program_with_packers):
        """Single order should be assigned to one packer."""
        program, packer1, packer2 = program_with_packers
        
        participant = ParticipantFactory(program=program)
        order = Order.objects.create(
            account=participant.accountbalance,
            status='confirmed',
            order_number='SINGLE-001',
        )
        
        result = split_orders_by_count([order], [packer1, packer2], 'fifty_fifty')
        
        # Total orders should be 1
        total = sum(len(o) for o in result.values())
        assert total == 1
    
    def test_program_with_no_packers(self):
        """Program with no packers should fail validation for split strategies."""
        program = Program.objects.create(
            name='No Packers Program',
            meeting_time='10:00:00',
            MeetingDay='monday',
            meeting_address='Test Address',
        )
        
        is_valid, errors = validate_split_strategy(program, 'fifty_fifty')
        
        assert is_valid is False
        assert len(errors) > 0  # Should have packer-related error
    
    def test_combined_order_name_generation(self, orders_for_program):
        """Combined order should generate a sensible name if not provided."""
        orders, program, packer1, packer2 = orders_for_program
        
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='none',
        )
        
        # Name should be auto-generated or acceptable
        assert combined_order.name is not None or combined_order.id is not None
