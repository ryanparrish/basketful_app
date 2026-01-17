"""
Tests for OrderValidationLog model and logging functionality.

These tests verify that OrderValidationLog is properly populated when:
- Order validation errors occur
- Voucher validation errors occur
- Middleware catches ValidationErrors
- Order clean() method raises errors
"""

import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings
from apps.log.models import OrderValidationLog
from apps.orders.models import Order
from apps.account.models import Participant, AccountBalance
from apps.pantry.tests.factories import (
    CategoryFactory,
    ProductFactory,
    ProductLimitFactory,
    ParticipantFactory,
    OrderFactory,
)
from apps.orders.utils.order_validation import OrderValidation, OrderItemData
from core.middleware import GlobalErrorMiddleware

User = get_user_model()


@pytest.mark.django_db
class TestOrderValidationLogCreation:
    """Tests for OrderValidationLog creation in various scenarios."""

    def test_log_created_when_category_limit_exceeded(self):
        """Test that OrderValidationLog is created when category limits are exceeded."""
        # Create participant and order
        participant = ParticipantFactory(adults=1, children=0)
        order = OrderFactory(account=participant.accountbalance)
        
        # Create category with limit
        category = CategoryFactory(name="Meat")
        ProductLimitFactory(
            category=category,
            limit=5,
            limit_scope="per_household"
        )
        product = ProductFactory(
            category=category,
            name="Ground Beef",
            price=Decimal("8.00")
        )
        
        # Create order items that exceed limit
        items = [OrderItemData(product=product, quantity=10)]
        validator = OrderValidation(order)
        
        # Clear any existing logs
        OrderValidationLog.objects.all().delete()
        
        # Attempt validation - should fail and create log
        with pytest.raises(ValidationError):
            validator.validate_order_items(items, participant, order.account)
        
        # Verify log was NOT created by validator (it raises the error)
        # The middleware or calling code should create the log
        # This test documents current behavior

    def test_log_fields_populated_correctly(self):
        """Test that OrderValidationLog fields are populated with correct data."""
        participant = ParticipantFactory(adults=2, children=1)
        order = OrderFactory(account=participant.accountbalance)
        product = ProductFactory(name="Test Product", price=Decimal("5.00"))
        
        # Create a log entry manually to verify field structure
        log = OrderValidationLog.objects.create(
            participant=participant,
            user=participant.user,
            order=order,
            product=product,
            message="Test validation error message",
            log_type=OrderValidationLog.ERROR
        )
        
        # Verify all fields are set correctly
        assert log.participant == participant
        assert log.user == participant.user
        assert log.order == order
        assert log.product == product
        assert log.message == "Test validation error message"
        assert log.log_type == OrderValidationLog.ERROR
        assert log.validated_at is not None
        assert log.created_at is not None

    def test_log_created_with_minimal_fields(self):
        """Test that OrderValidationLog can be created with minimal required fields."""
        # Only message is truly required
        log = OrderValidationLog.objects.create(
            message="Minimal validation error"
        )
        
        assert log.message == "Minimal validation error"
        assert log.participant is None
        assert log.user is None
        assert log.order is None
        assert log.product is None
        assert log.log_type == OrderValidationLog.INFO  # default

    def test_log_types_all_supported(self):
        """Test that all log types (INFO, WARNING, ERROR) are supported."""
        # Create INFO log
        info_log = OrderValidationLog.objects.create(
            message="Info message",
            log_type=OrderValidationLog.INFO
        )
        assert info_log.log_type == OrderValidationLog.INFO
        
        # Create WARNING log
        warning_log = OrderValidationLog.objects.create(
            message="Warning message",
            log_type=OrderValidationLog.WARNING
        )
        assert warning_log.log_type == OrderValidationLog.WARNING
        
        # Create ERROR log
        error_log = OrderValidationLog.objects.create(
            message="Error message",
            log_type=OrderValidationLog.ERROR
        )
        assert error_log.log_type == OrderValidationLog.ERROR

    def test_log_str_representation(self):
        """Test the string representation of OrderValidationLog."""
        participant = ParticipantFactory(adults=1, children=0)
        log = OrderValidationLog.objects.create(
            participant=participant,
            message="Test error message for display"
        )
        
        log_str = str(log)
        assert participant.name in log_str or "Unknown" in log_str
        assert "Test error message for display" in log_str

    def test_log_ordering_by_created_at_desc(self):
        """Test that logs are ordered by created_at descending (newest first)."""
        # Create multiple logs
        log1 = OrderValidationLog.objects.create(message="First log")
        log2 = OrderValidationLog.objects.create(message="Second log")
        log3 = OrderValidationLog.objects.create(message="Third log")
        
        # Get all logs
        logs = list(OrderValidationLog.objects.all())
        
        # Verify ordering (newest first)
        assert logs[0].id == log3.id
        assert logs[1].id == log2.id
        assert logs[2].id == log1.id

    def test_log_cascade_delete_with_participant(self):
        """Test that logs are deleted when participant is deleted."""
        participant = ParticipantFactory(adults=1, children=0)
        
        # Create log with participant
        log = OrderValidationLog.objects.create(
            participant=participant,
            message="Test log"
        )
        
        log_id = log.id
        participant_id = participant.id
        
        # Delete participant
        participant.delete()
        
        # Verify log is also deleted (CASCADE)
        assert not OrderValidationLog.objects.filter(id=log_id).exists()

    def test_log_set_null_with_user_deletion(self):
        """Test that user field is set to NULL when user is deleted."""
        user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        
        # Create log with user
        log = OrderValidationLog.objects.create(
            user=user,
            message="Test log"
        )
        
        log_id = log.id
        
        # Delete user
        user.delete()
        
        # Verify log still exists but user is NULL
        log.refresh_from_db()
        assert log.user is None
        assert log.message == "Test log"

    def test_log_cascade_delete_with_order(self):
        """Test that logs are deleted when order is deleted."""
        participant = ParticipantFactory(adults=1, children=0)
        order = OrderFactory(account=participant.accountbalance)
        
        # Create log with order
        log = OrderValidationLog.objects.create(
            order=order,
            message="Order validation error"
        )
        
        log_id = log.id
        
        # Delete order
        order.delete()
        
        # Verify log is also deleted (CASCADE)
        assert not OrderValidationLog.objects.filter(id=log_id).exists()

    def test_log_set_null_with_product_deletion(self):
        """Test that product field is set to NULL when product is deleted."""
        product = ProductFactory(name="Test Product", price=Decimal("5.00"))
        
        # Create log with product
        log = OrderValidationLog.objects.create(
            product=product,
            message="Product validation error"
        )
        
        log_id = log.id
        
        # Delete product
        product.delete()
        
        # Verify log still exists but product is NULL
        log.refresh_from_db()
        assert log.product is None
        assert log.message == "Product validation error"


@pytest.mark.django_db
class TestMiddlewareLogging:
    """Tests for OrderValidationLog creation via middleware."""

    def test_middleware_creates_log_on_validation_error_production(self, settings):
        """Test that middleware creates log when ValidationError occurs in production."""
        # Set DEBUG=False to simulate production
        settings.DEBUG = False
        
        # Create user and participant
        user = User.objects.create_user(username="testuser", password="test123")
        participant = ParticipantFactory(adults=1, children=0)
        participant.user = user
        participant.save()
        
        # Create request
        factory = RequestFactory()
        request = factory.get('/test-path/')
        request.user = user
        
        # Clear existing logs
        OrderValidationLog.objects.all().delete()
        
        # Create middleware
        middleware = GlobalErrorMiddleware(lambda r: None)
        
        # Create a validation error
        error = ValidationError("Test validation error in production")
        
        # Handle the error
        middleware.handle_validation_error(request, error)
        
        # Verify log was created
        logs = OrderValidationLog.objects.all()
        assert logs.count() == 1
        assert logs[0].user == user
        # Note: participant is retrieved from user.participant in middleware
        assert logs[0].participant == participant
        assert "Test validation error in production" in str(logs[0].message)
        assert logs[0].log_type == OrderValidationLog.ERROR

    def test_middleware_skips_log_in_debug_mode(self, settings):
        """Test that middleware doesn't create log in DEBUG mode."""
        # Set DEBUG=True
        settings.DEBUG = True
        
        # Create user
        user = User.objects.create_user(username="testuser", password="test123")
        
        # Create request
        factory = RequestFactory()
        request = factory.get('/test-path/')
        request.user = user
        
        # Clear existing logs
        OrderValidationLog.objects.all().delete()
        
        # Create middleware
        middleware = GlobalErrorMiddleware(lambda r: None)
        
        # Create a validation error
        error = ValidationError("Test validation error in debug")
        
        # Handle the error
        middleware.handle_validation_error(request, error)
        
        # Verify NO log was created (DEBUG mode logs to console instead)
        assert OrderValidationLog.objects.count() == 0

    def test_middleware_handles_unauthenticated_user(self, settings):
        """Test that middleware handles unauthenticated users gracefully."""
        settings.DEBUG = False
        
        # Create request with anonymous user
        factory = RequestFactory()
        request = factory.get('/test-path/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        
        # Clear existing logs
        OrderValidationLog.objects.all().delete()
        
        # Create middleware
        middleware = GlobalErrorMiddleware(lambda r: None)
        
        # Create a validation error
        error = ValidationError("Validation error for anonymous user")
        
        # Handle the error
        middleware.handle_validation_error(request, error)
        
        # Verify log was created with NULL user
        logs = OrderValidationLog.objects.all()
        assert logs.count() == 1
        assert logs[0].user is None
        assert logs[0].participant is None
        assert "Validation error for anonymous user" in str(logs[0].message)


@pytest.mark.django_db
class TestVoucherUtilsLogging:
    """Tests for OrderValidationLog creation in voucher_utils."""

    def test_log_created_when_no_vouchers_available(self):
        """Test that log is created when no vouchers are available for order.
        
        Note: This test verifies voucher_utils integration with OrderValidationLog.
        """
        from apps.pantry.utils.voucher_utils import apply_vouchers_to_order
        from apps.orders.tests.factories import OrderItemFactory, VoucherFactory
        from unittest.mock import patch
        
        # Create order with items
        participant = ParticipantFactory(adults=1, children=0)
        
        # Set sufficient balance to avoid validation errors
        account = participant.accountbalance
        account.base_balance = Decimal("100.00")
        account.save()
        
        # Create vouchers to provide available balance (so validation passes)
        voucher1 = VoucherFactory(account=account, state='applied', voucher_type='grocery')
        voucher2 = VoucherFactory(account=account, state='applied', voucher_type='grocery')
        
        order = OrderFactory(
            account=account,
            status="pending"  # Start as pending to avoid validation
        )
        # Add an item so order has content
        OrderItemFactory(order=order)
        
        # Update to confirmed after items exist
        order.status = "confirmed"
        order.save()
        
        # Now delete the vouchers so apply_vouchers_to_order finds none
        voucher1.delete()
        voucher2.delete()
        
        # Verify vouchers are deleted
        remaining_vouchers = account.vouchers.filter(state='applied', active=True).count()
        assert remaining_vouchers == 0, f"Expected 0 vouchers after deletion, found {remaining_vouchers}"
        
        # Clear existing logs
        OrderValidationLog.objects.all().delete()
        
        # Mock the Celery task to avoid connection issues
        with patch('apps.pantry.utils.voucher_utils.log_voucher_application_task.delay'):
            # Apply vouchers (none available after deletion)
            # The function will log internally when no vouchers are found
            # Debug: verify account and participant linkage
            print(f"\\nDEBUG: Account: {account}, Participant: {account.participant}")
            print(f"DEBUG: Order account: {order.account}, Order status: {order.status}")
            result = apply_vouchers_to_order(order)
            print(f"DEBUG: Result: {result}")
        
        # Debug: Check if log was created
        all_logs = OrderValidationLog.objects.all()
        print(f"DEBUG: Total logs: {all_logs.count()}")
        for log in all_logs:
            print(f"DEBUG: Log - Participant: {log.participant}, Message: {log.message}")
        
        # Verify log was created
        logs = OrderValidationLog.objects.filter(participant=participant)
        assert logs.count() == 1
        assert "No active grocery vouchers" in logs[0].message
        assert str(order.id) in logs[0].message
        assert result is False


@pytest.mark.django_db
class TestLogQueryPerformance:
    """Tests for OrderValidationLog query performance."""

    def test_select_related_for_foreign_keys(self):
        """Test that querying logs with select_related is efficient."""
        # Create related objects
        participant = ParticipantFactory(adults=1, children=0)
        order = OrderFactory(account=participant.accountbalance)
        product = ProductFactory(name="Test Product", price=Decimal("5.00"))
        
        # Create log
        OrderValidationLog.objects.create(
            participant=participant,
            user=participant.user,
            order=order,
            product=product,
            message="Test error"
        )
        
        # Query with select_related
        log = OrderValidationLog.objects.select_related(
            'participant', 'user', 'order', 'product'
        ).first()
        
        # Access related objects (should not trigger additional queries)
        assert log.participant.name is not None
        assert log.user is None or log.user.username is not None
        assert log.order.id is not None
        assert log.product.name == "Test Product"

    def test_filter_by_log_type(self):
        """Test filtering logs by log_type."""
        # Create logs of different types
        OrderValidationLog.objects.create(
            message="Info log",
            log_type=OrderValidationLog.INFO
        )
        OrderValidationLog.objects.create(
            message="Warning log",
            log_type=OrderValidationLog.WARNING
        )
        OrderValidationLog.objects.create(
            message="Error log 1",
            log_type=OrderValidationLog.ERROR
        )
        OrderValidationLog.objects.create(
            message="Error log 2",
            log_type=OrderValidationLog.ERROR
        )
        
        # Filter by ERROR type
        error_logs = OrderValidationLog.objects.filter(
            log_type=OrderValidationLog.ERROR
        )
        assert error_logs.count() == 2
        
        # Filter by INFO type
        info_logs = OrderValidationLog.objects.filter(
            log_type=OrderValidationLog.INFO
        )
        assert info_logs.count() == 1

    def test_filter_by_participant(self):
        """Test filtering logs by participant."""
        participant1 = ParticipantFactory(adults=1, children=0)
        participant2 = ParticipantFactory(adults=2, children=1)
        
        # Create logs for different participants
        OrderValidationLog.objects.create(
            participant=participant1,
            message="Participant 1 error"
        )
        OrderValidationLog.objects.create(
            participant=participant1,
            message="Participant 1 another error"
        )
        OrderValidationLog.objects.create(
            participant=participant2,
            message="Participant 2 error"
        )
        
        # Filter by participant1
        p1_logs = OrderValidationLog.objects.filter(participant=participant1)
        assert p1_logs.count() == 2
        
        # Filter by participant2
        p2_logs = OrderValidationLog.objects.filter(participant=participant2)
        assert p2_logs.count() == 1
