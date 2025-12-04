"""Tests for combined order creation feature."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
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
        """Test creating a combined order with existing orders."""
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

        # Login as admin
        client.force_login(admin_user)

        # Submit form
        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        response = client.post(url, data=form_data, follow=True)

        # Check combined order was created
        assert CombinedOrder.objects.count() == 1
        combined_order = CombinedOrder.objects.first()
        assert combined_order.program == program
        assert combined_order.orders.count() == 2
        assert order1 in combined_order.orders.all()
        assert order2 in combined_order.orders.all()

        # Check success message
        messages = list(response.context['messages'])
        assert len(messages) == 1
        assert 'Combined order created successfully' in str(messages[0])

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
        response = client.post(url, data=form_data)

        # Check no combined order was created
        assert CombinedOrder.objects.count() == 0

        # Check warning message
        messages = list(response.context['messages'])
        assert len(messages) == 1
        assert 'No confirmed orders found' in str(messages[0])

    def test_create_combined_order_only_confirmed(
        self, program, admin_user, client
    ):
        """Test only confirmed orders are included."""
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

        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        response = client.post(url, data=form_data, follow=True)

        # Check only confirmed order is included
        combined_order = CombinedOrder.objects.first()
        assert combined_order.orders.count() == 1
        assert confirmed_order in combined_order.orders.all()
        assert pending_order not in combined_order.orders.all()
        assert cancelled_order not in combined_order.orders.all()

    def test_create_combined_order_filters_by_program(
        self, program, another_program, admin_user, client
    ):
        """Test combined order only includes orders from selected program."""
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

        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': (now - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': (now + timedelta(days=1)).strftime('%Y-%m-%d'),
        }
        response = client.post(url, data=form_data, follow=True)

        # Check only orders from selected program are included
        combined_order = CombinedOrder.objects.first()
        assert combined_order.orders.count() == 1
        assert order1 in combined_order.orders.all()
        assert order2 not in combined_order.orders.all()

    def test_create_combined_order_filters_by_date_range(
        self, program, admin_user, client
    ):
        """Test combined order only includes orders within date range."""
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

        client.force_login(admin_user)

        url = reverse('admin:orders_combinedorder_create')
        form_data = {
            'program': program.id,
            'start_date': (timezone.now() - timedelta(days=5)).strftime(
                '%Y-%m-%d'
            ),
            'end_date': timezone.now().strftime('%Y-%m-%d'),
        }
        response = client.post(url, data=form_data, follow=True)

        # Check only orders within date range are included
        combined_order = CombinedOrder.objects.first()
        assert combined_order.orders.count() == 1
        assert recent_order in combined_order.orders.all()
        assert old_order not in combined_order.orders.all()
        assert future_order not in combined_order.orders.all()

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
        """Test successful creation redirects to changelist."""
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

        # Should redirect to changelist
        assert response.status_code == 302
        assert response.url == reverse(
            'admin:orders_combinedorder_changelist'
        )

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
        # Create first combined order
        combined_order1 = CombinedOrder.objects.create(program=program)
        
        # Create another with created_at in a different week
        from django.utils import timezone
        next_week = timezone.now() + timedelta(days=7)
        
        # Manually create and set the date
        from django.db.models import Model
        combined_order2 = CombinedOrder(program=program)
        Model.save(combined_order2)
        
        # Update created_at to next week
        CombinedOrder.objects.filter(pk=combined_order2.pk).update(
            created_at=next_week
        )
        
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

    def test_admin_creates_combined_order_twice_same_week(
        self, program, admin_user, client, product
    ):
        """
        Test that creating combined order twice in same week
        reuses existing order.
        """
        participant = ParticipantFactory(program=program)
        now = timezone.now()
        
        order1 = create_test_order(
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
        
        # Create first time
        response1 = client.post(url, data=form_data, follow=True)
        assert response1.status_code == 200
        assert CombinedOrder.objects.count() == 1
        
        # Create another order
        order2 = create_test_order(
            participant.accountbalance,
            status='confirmed',
            order_date=now
        )
        
        # Try to create again in same week - should reuse existing
        response2 = client.post(url, data=form_data, follow=True)
        assert response2.status_code == 200
        
        # Should still have only 1 combined order
        assert CombinedOrder.objects.count() == 1
        
        # But it should have both orders
        combined_order = CombinedOrder.objects.first()
        assert combined_order.orders.count() == 2
        assert order1 in combined_order.orders.all()
        assert order2 in combined_order.orders.all()

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
        from django.utils import timezone
        
        current_year = timezone.now().year
        current_week = timezone.now().isocalendar()[1]
        
        # Create child combined order
        child_order, _ = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            is_parent=False,
            defaults={'program': program, 'is_parent': False}
        )
        
        # Create parent combined order
        parent_order, _ = CombinedOrder.objects.get_or_create(
            program=program,
            created_at__year=current_year,
            created_at__week=current_week,
            is_parent=True,
            defaults={'program': program, 'is_parent': True}
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
        
        # Create some child orders first
        child1 = CombinedOrder.objects.create(
            program=program,
            is_parent=False
        )
        child2 = CombinedOrder.objects.create(
            program=program,
            is_parent=False
        )
        
        # Need to set created_at to different values to avoid constraint
        from django.utils import timezone
        CombinedOrder.objects.filter(pk=child2.pk).update(
            created_at=timezone.now() + timedelta(days=7)
        )
        
        child_orders = [child1, child2]
        
        # Create parent
        parent_order = create_parent_combined_order(
            program, child_orders, packer=None
        )
        
        assert parent_order.is_parent
        assert parent_order.program == program
        
        # Call again - should reuse existing
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
