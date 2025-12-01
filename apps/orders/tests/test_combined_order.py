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
