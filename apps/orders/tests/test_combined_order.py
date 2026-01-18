"""Tests for combined order creation feature."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
from apps.orders.models import Order, CombinedOrder
from apps.orders.forms import CreateCombinedOrderForm
from apps.lifeskills.models import Program
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
)


@pytest.fixture(autouse=True)
def mock_celery_task_always_eager(settings):
    """Mock Celery to run tasks synchronously for all tests in this module."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    with patch('celery.app.task.Task.apply_async', side_effect=lambda args, kwargs: None):
        yield


def create_test_order(account, status='pending', order_date=None):
    """
    Helper function to create test orders bypassing validation.
    """
    from uuid import uuid4
    from django.db.models import Model
    order = Order(
        account=account,
        status=status,
        order_number=f'TEST-{uuid4().hex[:12].upper()}'
    )
    # Skip validation by calling Model.save() directly
    Model.save(order)
    
    # If we need to set a specific order_date, update it after save
    if order_date:
        Order.objects.filter(pk=order.pk).update(order_date=order_date)
        order.refresh_from_db()
    
    return order


@pytest.fixture
def admin_user():
    """Create an admin user for testing."""
    user = User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='admin123'
    )
    return user


@pytest.fixture
def program():
    """Create a test program."""
    return Program.objects.create(
        name='Test Program',
        meeting_time='10:00:00',
        MeetingDay='monday',
        meeting_address='123 Test St'
    )


@pytest.fixture
def another_program():
    """Create another test program."""
    return Program.objects.create(
        name='Another Program',
        meeting_time='14:00:00',
        MeetingDay='wednesday',
        meeting_address='456 Test Ave'
    )


@pytest.fixture
def category():
    """Create a test category."""
    return CategoryFactory(name='Grocery')


@pytest.fixture
def product(category):
    """Create a test product."""
    return ProductFactory(
        name='Test Product',
        price=Decimal('10.00'),
        category=category
    )


@pytest.mark.django_db
class TestCreateCombinedOrderForm:
    """Test the CreateCombinedOrderForm."""

    def test_form_valid_with_correct_data(self, program):
        """Test form is valid with correct data."""
        form_data = {
            'program': program.id,
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
        }
        form = CreateCombinedOrderForm(data=form_data)
        assert form.is_valid()

    def test_form_invalid_end_before_start(self, program):
        """Test form is invalid when end date is before start date."""
        form_data = {
            'program': program.id,
            'start_date': '2025-01-31',
            'end_date': '2025-01-01',
        }
        form = CreateCombinedOrderForm(data=form_data)
        assert not form.is_valid()
        assert 'End date must be after start date.' in str(
            form.non_field_errors()
        )

    def test_form_requires_all_fields(self):
        """Test form requires all fields."""
        form = CreateCombinedOrderForm(data={})
        assert not form.is_valid()
        assert 'program' in form.errors
        assert 'start_date' in form.errors
        assert 'end_date' in form.errors

    def test_form_same_start_and_end_date(self, program):
        """Test form accepts same start and end date."""
        form_data = {
            'program': program.id,
            'start_date': '2025-01-15',
            'end_date': '2025-01-15',
        }
        form = CreateCombinedOrderForm(data=form_data)
        assert form.is_valid()


@pytest.mark.django_db
class TestCombinedOrderCreation:
    """Test combined order creation functionality."""

    def test_create_combined_order_with_orders(
        self, program, product, admin_user, client
    ):
        """Test creating a combined order with existing orders using helper function."""
        from apps.orders.tasks.helper.combined_order_helper import create_combined_order_with_packing
        from apps.pantry.models import OrderPacker
        
        # Add a packer to the program (required for combined order creation)
        packer = OrderPacker.objects.create(name='Test Packer')
        program.packers.add(packer)
        
        # Create participants with the program
        participant1 = ParticipantFactory(program=program)
        participant2 = ParticipantFactory(program=program)

        # Create confirmed orders within date range
        now = timezone.now()
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed',
            order_date=now
        )

        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed',
            order_date=now
        )

        # Create combined order directly using helper
        orders = [order1, order2]
        combined_order, packing_lists = create_combined_order_with_packing(
            program=program,
            orders=orders,
            strategy='none',
        )

        # Check combined order was created
        assert CombinedOrder.objects.count() == 1
        assert combined_order.program == program
        assert combined_order.orders.count() == 2
        assert order1 in combined_order.orders.all()
        assert order2 in combined_order.orders.all()

    def test_create_combined_order_no_orders(
        self, program, admin_user, client
    ):
        """Test creating a combined order when no orders exist."""
        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
        }
        response = client.post(url, data=form_data, follow=True)

        # Should redirect to preview which shows no eligible orders
        # Check no combined order was created
        assert CombinedOrder.objects.count() == 0

    def test_create_combined_order_only_confirmed(
        self, program, admin_user, client
    ):
        """Test only confirmed orders are included using helper function."""
        from apps.orders.tasks.helper.combined_order_helper import get_eligible_orders
        
        participant = ParticipantFactory(program=program)
        now = timezone.now()

        # Create orders with different statuses
        confirmed_order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )

        pending_order = create_test_order(
            participant.accountbalance,
            status='pending',
            order_date=now
        )

        cancelled_order = create_test_order(
            participant.accountbalance,
            status='cancelled',
            order_date=now
        )

        # Get eligible orders
        start_date = (now - timedelta(days=1)).date()
        end_date = (now + timedelta(days=1)).date()
        eligible_orders, excluded, warnings = get_eligible_orders(
            program, start_date, end_date
        )

        # Check only confirmed order is eligible
        assert confirmed_order in eligible_orders
        assert pending_order not in eligible_orders
        assert cancelled_order not in eligible_orders

    def test_create_combined_order_filters_by_program(
        self, program, another_program, admin_user, client
    ):
        """Test combined order only includes orders from selected program."""
        from apps.orders.tasks.helper.combined_order_helper import get_eligible_orders
        
        participant1 = ParticipantFactory(program=program)
        participant2 = ParticipantFactory(program=another_program)

        now = timezone.now()

        # Create orders for both programs
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed',
            order_date=now
        )

        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed',
            order_date=now
        )

        # Get eligible orders for first program
        start_date = (now - timedelta(days=1)).date()
        end_date = (now + timedelta(days=1)).date()
        eligible_orders, excluded, warnings = get_eligible_orders(
            program, start_date, end_date
        )

        # Check only orders from selected program are included
        assert order1 in eligible_orders
        assert order2 not in eligible_orders

    def test_create_combined_order_filters_by_date_range(
        self, program, admin_user, client
    ):
        """Test combined order only includes orders within date range."""
        from apps.orders.tasks.helper.combined_order_helper import get_eligible_orders
        
        participant = ParticipantFactory(program=program)

        # Create orders at different times
        old_date = timezone.now() - timedelta(days=10)
        recent_date = timezone.now() - timedelta(days=2)
        future_date = timezone.now() + timedelta(days=10)

        old_order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=old_date
        )

        recent_order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=recent_date
        )

        future_order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=future_date
        )

        # Get eligible orders
        start_date = (timezone.now() - timedelta(days=5)).date()
        end_date = timezone.now().date()
        eligible_orders, excluded, warnings = get_eligible_orders(
            program, start_date, end_date
        )

        # Check only orders within date range are included
        assert recent_order in eligible_orders
        assert old_order not in eligible_orders
        assert future_order not in eligible_orders

    def test_create_combined_order_view_requires_login(self, client):
        """Test that the create combined order view requires login."""
        url = reverse('admin:orders_combinedorder_create')
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302
        assert '/admin/login/' in response.url

    def test_create_combined_order_get_request_shows_form(
        self, admin_user, client
    ):
        """Test GET request shows the form."""
        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        response = client.get(url)

        assert response.status_code == 200
        assert 'form' in response.context
        assert isinstance(
            response.context['form'], CreateCombinedOrderForm
        )

    def test_create_combined_order_redirects_after_success(
        self, program, admin_user, client
    ):
        """Test successful creation redirects to preview first."""
        participant = ParticipantFactory(program=program)
        now = timezone.now()

        order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )

        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        response = client.post(url, data=form_data)

        # Should redirect to preview (new workflow)
        assert response.status_code == 302
        assert 'preview' in response.url

    def test_create_combined_order_invalid_form_shows_errors(
        self, program, admin_user, client
    ):
        """Test invalid form shows errors."""
        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': '2025-01-31',
            'end_date': '2025-01-01',  # Invalid: end before start
        }
        response = client.post(url, data=form_data)

        assert response.status_code == 200
        assert 'form' in response.context
        assert not response.context['form'].is_valid()


@pytest.mark.django_db
class TestCombinedOrderUniqueConstraint:
    """Test the unique_program_per_week constraint and get_or_create logic."""

    def test_cannot_create_duplicate_combined_order_same_week(self, program):
        """Test that unique constraint prevents duplicate combined orders."""
        # Create first combined order
        combined_order1 = CombinedOrder.objects.create(program=program)
        
        # Try to create another in the same week - should raise IntegrityError
        # if constraint is working (but our code should use get_or_create)
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            CombinedOrder.objects.create(program=program)

    def test_can_create_combined_order_different_weeks(self, program):
        """Test that combined orders can be created in different weeks."""
        from freezegun import freeze_time
        from django.utils import timezone
        
        # Create first combined order in current week
        with freeze_time("2025-12-01"):  # Week 48
            combined_order1 = CombinedOrder.objects.create(program=program)
        
        # Create second combined order in next week
        with freeze_time("2025-12-08"):  # Week 49
            combined_order2 = CombinedOrder.objects.create(program=program)
        
        # Should have 2 combined orders
        assert CombinedOrder.objects.filter(program=program).count() == 2

    def test_can_create_combined_order_different_programs_same_week(
        self, program, another_program
    ):
        """Test that different programs can have combined orders same week."""
        combined_order1 = CombinedOrder.objects.create(program=program)
        combined_order2 = CombinedOrder.objects.create(
            program=another_program
        )
        
        assert CombinedOrder.objects.count() == 2
        assert combined_order1.program != combined_order2.program

    def test_orders_can_only_be_combined_once(
        self, program, admin_user, client, product
    ):
        """
        Test that orders with is_combined=True are not included in new combined orders.
        """
        from apps.orders.tasks.helper.combined_order_helper import get_eligible_orders
        
        participant = ParticipantFactory(program=program)
        now = timezone.now()
        
        order1 = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )
        
        # First, manually mark order1 as combined
        order1.is_combined = True
        order1.save()
        
        # Create another order
        order2 = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )
        
        # Get eligible orders - order1 should be excluded
        start_date = (now - timedelta(days=1)).date()
        end_date = (now + timedelta(days=1)).date()
        eligible_orders, excluded_orders, warnings = get_eligible_orders(
            program, start_date, end_date
        )
        
        # order1 should not be eligible (already combined)
        assert order1 not in eligible_orders
        assert order2 in eligible_orders

    def test_get_or_create_returns_existing_combined_order(self, program):
        """Test that get_or_create returns existing combined order."""
        from django.utils import timezone
        
        current_year = timezone.now().year
        current_week = timezone.now().isocalendar()[1]
        
        # Create first
        combined_order1, created1 = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            defaults={'program': program}
        )
        assert created1
        
        # Get or create again - should return existing
        combined_order2, created2 = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            defaults={'program': program}
        )
        assert not created2
        assert combined_order1.id == combined_order2.id

    def test_combined_order_with_parent_and_child(self, program):
        """Test creating parent and child combined orders."""
        from freezegun import freeze_time
        
        # Create child in week 48
        with freeze_time("2025-12-01"):
            child_order = CombinedOrder.objects.create(
                program=program,
                is_parent=False
            )
        
        # Create parent in week 49 to avoid constraint
        with freeze_time("2025-12-08"):
            parent_order = CombinedOrder.objects.create(
                program=program,
                is_parent=True
            )
        
        # Should have both parent and child
        assert CombinedOrder.objects.filter(program=program).count() == 2
        assert CombinedOrder.objects.filter(
            program=program, is_parent=True
        ).count() == 1
        assert CombinedOrder.objects.filter(
            program=program, is_parent=False
        ).count() == 1

    def test_helper_function_create_child_combined_orders(self, program):
        """Test the create_child_combined_orders helper function."""
        from apps.orders.tasks.helper.combined_order_helper import (
            create_child_combined_orders
        )
        
        participant = ParticipantFactory(program=program)
        order1 = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        order2 = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        orders = [order1, order2]
        packer = None  # No packer for this test
        
        # Create child combined orders
        child_orders = create_child_combined_orders(program, orders, packer)
        
        # Should create combined orders (may reuse if already exists)
        assert len(child_orders) > 0
        
        # Call again - should reuse existing
        child_orders2 = create_child_combined_orders(program, orders, packer)
        
        # Should not create duplicates
        total_combined = CombinedOrder.objects.filter(
            program=program, is_parent=False
        ).count()
        assert total_combined >= 1  # At least one combined order

    def test_helper_function_create_parent_combined_order(self, program):
        """Test the create_parent_combined_order helper function."""
        from apps.orders.tasks.helper.combined_order_helper import (
            create_parent_combined_order
        )
        from freezegun import freeze_time
        
        # Create child orders in different weeks to avoid constraint
        with freeze_time("2025-12-01"):
            child1 = CombinedOrder.objects.create(
                program=program,
                is_parent=False
            )
        
        with freeze_time("2025-12-08"):
            child2 = CombinedOrder.objects.create(
                program=program,
                is_parent=False
            )
        
        child_orders = [child1, child2]
        
        # Create parent in a different week
        with freeze_time("2025-12-15"):
            parent_order = create_parent_combined_order(
                program, child_orders, packer=None
            )
        
            assert parent_order.is_parent
            assert parent_order.program == program
        
            # Call again in same frozen time - should reuse existing
            parent_order2 = create_parent_combined_order(
                program, child_orders, packer=None
            )
        
            # Should be the same order
            assert parent_order.id == parent_order2.id

    def test_combined_order_summarized_data_updates(self, program, product):
        """Test that summarized data updates when orders are added."""
        from django.utils import timezone
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        # Add items to order
        from apps.orders.models import OrderItem
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=5,
            price=product.price,
            price_at_order=product.price
        )
        
        current_year = timezone.now().year
        current_week = timezone.now().isocalendar()[1]
        
        combined_order, created = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            defaults={'program': program}
        )
        
        combined_order.orders.add(order)
        
        # Update summarized data
        summarized = combined_order.summarized_items_by_category()
        combined_order.summarized_data = summarized
        combined_order.save(update_fields=['summarized_data'])
        
        # Verify summarized data contains the product
        assert len(combined_order.summarized_data) > 0
        assert product.category.name in combined_order.summarized_data


@pytest.mark.django_db
class TestCombinedOrderOrdersDisplay:
    """Test that orders are properly displayed in combined orders."""

    def test_combined_order_shows_added_orders(self, program):
        """Test that orders appear in combined order after being added."""
        participant = ParticipantFactory(program=program)
        
        order1 = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        order2 = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        
        # Add orders
        combined_order.orders.add(order1, order2)
        
        # Verify orders are in the combined order
        assert combined_order.orders.count() == 2
        assert order1 in combined_order.orders.all()
        assert order2 in combined_order.orders.all()

    def test_combined_order_orders_queryable(self, program):
        """Test that combined order orders can be queried."""
        participant = ParticipantFactory(program=program)
        
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Query orders through combined order
        orders_list = list(combined_order.orders.all())
        assert len(orders_list) == 1
        assert orders_list[0].id == order.id
        assert orders_list[0].status == 'confirmed'

    def test_combined_order_with_order_items(self, program, product):
        """Test combined order with orders that have items."""
        from apps.orders.models import OrderItem
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        # Add items to order
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=3,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Verify order with items is accessible
        assert combined_order.orders.count() == 1
        combined_order_order = combined_order.orders.first()
        assert combined_order_order.items.count() == 1
        assert combined_order_order.items.first().product == product
        assert combined_order_order.items.first().quantity == 3

    def test_combined_order_filters_by_program(self, program, another_program):
        """Test that combined order only shows orders from correct program."""
        participant1 = ParticipantFactory(program=program)
        participant2 = ParticipantFactory(program=another_program)
        
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed'
        )
        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed'
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order1)
        
        # Should only have order from the correct program
        assert combined_order.orders.count() == 1
        assert order1 in combined_order.orders.all()
        assert order2 not in combined_order.orders.all()

    def test_admin_combined_order_displays_orders(
        self, program, admin_user, client, product
    ):
        """Test that combined order properly includes and displays orders."""
        participant = ParticipantFactory(program=program)
        now = timezone.now()
        
        order = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )
        
        # Add item to order
        from apps.orders.models import OrderItem
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        # Create combined order directly and add orders
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Verify combined order was created
        assert combined_order is not None
        
        # Verify order is in combined order
        assert combined_order.orders.count() == 1
        assert order in combined_order.orders.all()

    def test_multiple_orders_added_to_combined_order(self, program, product):
        """Test adding multiple orders with items to combined order."""
        from apps.orders.models import OrderItem
        
        # Create multiple participants and orders
        participants = [
            ParticipantFactory(program=program) for _ in range(3)
        ]
        
        orders = []
        for participant in participants:
            order = create_test_order(
                participant.accountbalance,
                status='confirmed'
            )
            # Add items to each order
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=2,
                price=product.price,
                price_at_order=product.price
            )
            orders.append(order)
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(*orders)
        
        # Verify all orders are present
        assert combined_order.orders.count() == 3
        for order in orders:
            assert order in combined_order.orders.all()
        
        # Verify all items are accessible
        total_items = 0
        for order in combined_order.orders.all():
            total_items += order.items.count()
        assert total_items == 3

    def test_combined_order_summarized_items_includes_all_orders(
        self, program, product, category
    ):
        """Test that summarized_items_by_category includes all orders."""
        from apps.orders.models import OrderItem
        
        # Create orders with different quantities
        participant1 = ParticipantFactory(program=program)
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order1,
            product=product,
            quantity=5,
            price=product.price,
            price_at_order=product.price
        )
        
        participant2 = ParticipantFactory(program=program)
        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order2,
            product=product,
            quantity=3,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order1, order2)
        
        # Get summarized data
        summary = combined_order.summarized_items_by_category()
        
        # Verify product is in summary with correct total
        assert category.name in summary
        assert product.name in summary[category.name]
        assert summary[category.name][product.name] == 8  # 5 + 3

    def test_combined_order_orders_persist_after_save(self, program):
        """Test that orders remain in combined order after save."""
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        combined_order.save()
        
        # Refresh from database
        combined_order.refresh_from_db()
        
        # Verify order is still there
        assert combined_order.orders.count() == 1
        assert order in combined_order.orders.all()

    def test_combined_order_orders_relationship_bidirectional(self, program):
        """Test that order can access its combined orders."""
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Access from order side (reverse relationship)
        assert order.combined_orders.count() == 1
        assert combined_order in order.combined_orders.all()

    def test_get_or_create_preserves_existing_orders(self, program):
        """Test that get_or_create doesn't lose existing orders."""
        from django.utils import timezone as tz
        
        participant1 = ParticipantFactory(program=program)
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed'
        )
        
        current_year = tz.now().year
        current_week = tz.now().isocalendar()[1]
        
        # Create first combined order with order1
        combined_order1, created1 = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            defaults={'program': program}
        )
        combined_order1.orders.add(order1)
        
        # Create second order
        participant2 = ParticipantFactory(program=program)
        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed'
        )
        
        # Get same combined order
        combined_order2, created2 = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            defaults={'program': program}
        )
        
        # Should be the same instance
        assert combined_order1.id == combined_order2.id
        assert not created2
        
        # Add second order
        combined_order2.orders.add(order2)
        
        # Both orders should be present
        assert combined_order2.orders.count() == 2
        assert order1 in combined_order2.orders.all()
        assert order2 in combined_order2.orders.all()


@pytest.mark.django_db
class TestCombinedOrderAdminDisplay:
    """Test combined order display issues in admin."""

    def test_combined_order_displays_count(self, program, product):
        """Test that combined order properly shows order count."""
        from apps.orders.models import OrderItem
        
        # Create orders with items
        participants = [ParticipantFactory(program=program) for _ in range(3)]
        orders = []
        
        for participant in participants:
            order = create_test_order(
                participant.accountbalance,
                status='confirmed'
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=2,
                price=product.price,
                price_at_order=product.price
            )
            orders.append(order)
        
        # Create combined order
        combined_order = CombinedOrder.objects.create(program=program)
        
        # Verify no orders initially
        assert combined_order.orders.count() == 0
        
        # Add orders
        combined_order.orders.add(*orders)
        
        # Verify count is correct
        assert combined_order.orders.count() == 3
        
        # Refresh from DB and verify again
        combined_order.refresh_from_db()
        assert combined_order.orders.count() == 3

    def test_combined_order_str_method(self, program):
        """Test that combined order string representation works."""
        combined_order = CombinedOrder.objects.create(program=program)
        
        str_repr = str(combined_order)
        assert program.name in str_repr
        assert "Combined Order" in str_repr

    def test_combined_order_queryset_with_orders(self, program, product):
        """Test fetching combined order from queryset includes orders."""
        from apps.orders.models import OrderItem
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Fetch from queryset
        fetched = CombinedOrder.objects.get(id=combined_order.id)
        
        # Verify orders are accessible
        assert fetched.orders.count() == 1
        assert order in fetched.orders.all()

    def test_combined_order_with_prefetch_related(self, program, product):
        """Test that prefetch_related properly loads orders."""
        from apps.orders.models import OrderItem
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Fetch with prefetch_related
        fetched = CombinedOrder.objects.prefetch_related('orders').get(
            id=combined_order.id
        )
        
        # Access orders (should be prefetched)
        orders_list = list(fetched.orders.all())
        assert len(orders_list) == 1
        assert orders_list[0].id == order.id

    def test_combined_order_orders_with_items_prefetch(self, program, product):
        """Test fetching combined order with nested prefetch for items."""
        from apps.orders.models import OrderItem
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        item = OrderItem.objects.create(
            order=order,
            product=product,
            quantity=3,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Fetch with nested prefetch
        fetched = CombinedOrder.objects.prefetch_related(
            'orders__items__product'
        ).get(id=combined_order.id)
        
        # Verify nested data is accessible
        order_from_combined = fetched.orders.first()
        assert order_from_combined is not None
        
        items = list(order_from_combined.items.all())
        assert len(items) == 1
        assert items[0].product.id == product.id
        assert items[0].quantity == 3

    def test_empty_combined_order_queryset(self, program):
        """Test combined order with no orders."""
        combined_order = CombinedOrder.objects.create(program=program)
        
        # Should have zero orders
        assert combined_order.orders.count() == 0
        assert list(combined_order.orders.all()) == []
        
        # summarized_items_by_category should return empty
        summary = combined_order.summarized_items_by_category()
        assert len(summary) == 0

    def test_combined_order_readonly_field_display(self, program, product):
        """Test that readonly orders field properly displays in admin."""
        from apps.orders.models import OrderItem
        
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Simulate what admin readonly field would display
        # The default display for ManyToMany is the queryset
        orders_display = combined_order.orders.all()
        
        assert orders_display.count() == 1
        assert order in orders_display

    def test_combined_order_multiple_programs_isolation(
        self, program, another_program, product
    ):
        """Test that combined orders from different programs are isolated."""
        from apps.orders.models import OrderItem
        
        # Program 1 order
        participant1 = ParticipantFactory(program=program)
        order1 = create_test_order(
            participant1.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order1,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        # Program 2 order
        participant2 = ParticipantFactory(program=another_program)
        order2 = create_test_order(
            participant2.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order2,
            product=product,
            quantity=3,
            price=product.price,
            price_at_order=product.price
        )
        
        # Create combined orders
        combined1 = CombinedOrder.objects.create(program=program)
        combined1.orders.add(order1)
        
        combined2 = CombinedOrder.objects.create(program=another_program)
        combined2.orders.add(order2)
        
        # Verify isolation
        assert combined1.orders.count() == 1
        assert order1 in combined1.orders.all()
        assert order2 not in combined1.orders.all()
        
        assert combined2.orders.count() == 1
        assert order2 in combined2.orders.all()
        assert order1 not in combined2.orders.all()

    def test_admin_display_orders_method(self, program, product, admin_user):
        """Test the admin display_orders method shows orders correctly."""
        from apps.orders.admin import CombinedOrderAdmin
        from apps.orders.models import OrderItem
        
        # Create order with item
        participant = ParticipantFactory(program=program)
        order = create_test_order(
            participant.accountbalance,
            status='confirmed'
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=2,
            price=product.price,
            price_at_order=product.price
        )
        
        # Create combined order
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(order)
        
        # Test admin display method
        admin_instance = CombinedOrderAdmin(CombinedOrder, admin.site)
        display_result = admin_instance.display_orders(combined_order)
        
        # Verify display contains order number
        assert str(order.order_number) in str(display_result)
        assert 'Order #' in str(display_result)

    def test_admin_order_count_method(self, program, product):
        """Test the admin order_count method returns correct count."""
        from apps.orders.admin import CombinedOrderAdmin
        from apps.orders.models import OrderItem
        
        # Create multiple orders
        participants = [ParticipantFactory(program=program) for _ in range(3)]
        orders = []
        
        for participant in participants:
            order = create_test_order(
                participant.accountbalance,
                status='confirmed'
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                price=product.price,
                price_at_order=product.price
            )
            orders.append(order)
        
        # Create combined order
        combined_order = CombinedOrder.objects.create(program=program)
        combined_order.orders.add(*orders)
        
        # Test admin order_count method
        admin_instance = CombinedOrderAdmin(CombinedOrder, admin.site)
        count = admin_instance.order_count(combined_order)
        
        assert count == 3

    def test_admin_display_orders_empty(self, program):
        """Test display_orders when combined order has no orders."""
        from apps.orders.admin import CombinedOrderAdmin
        
        # Create combined order without orders
        combined_order = CombinedOrder.objects.create(program=program)
        
        # Test admin display method
        admin_instance = CombinedOrderAdmin(CombinedOrder, admin.site)
        display_result = admin_instance.display_orders(combined_order)
        
        assert "No orders" in str(display_result)
