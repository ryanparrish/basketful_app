"""
Tests for order success view and edge cases with validation.

This module tests:
- Order success page rendering
- Error handling when updating success_viewed flag
- Validation bypass with update_fields
- Edge cases with balance validation after order creation
"""
import logging
from decimal import Decimal
from unittest.mock import patch, Mock

import pytest
from django.urls import reverse
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError

from apps.orders.models import Order, OrderItem, OrderValidationLog
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
)
from apps.account.models import AccountBalance

logger = logging.getLogger(__name__)


@pytest.fixture
def user_with_order(db):
    """Create a user with participant and a completed order."""
    user = UserFactory()
    participant = ParticipantFactory(user=user)
    
    # Get or create the account for the participant
    account, created = AccountBalance.objects.get_or_create(
        participant=participant,
        defaults={'base_balance': Decimal("100.00")}
    )
    if not created:
        account.base_balance = Decimal("100.00")
        account.save()
    
    # Create category and products
    category = CategoryFactory(name="Food")
    product1 = ProductFactory(category=category, price=Decimal("10.00"))
    product2 = ProductFactory(category=category, price=Decimal("15.00"))
    
    # Create order
    order = Order.objects.create(
        user=user,
        account=account,
        status="confirmed"
    )
    
    OrderItem.objects.create(
        order=order,
        product=product1,
        quantity=2,
        price=product1.price,
        price_at_order=product1.price
    )
    OrderItem.objects.create(
        order=order,
        product=product2,
        quantity=1,
        price=product2.price,
        price_at_order=product2.price
    )
    
    return {
        'user': user,
        'participant': participant,
        'account': account,
        'order': order,
        'products': [product1, product2]
    }


@pytest.mark.django_db
class TestOrderSuccessView:
    """Test suite for order_success view."""
    
    def test_order_success_displays_correctly(self, client, user_with_order):
        """Test that order success page displays correctly."""
        user = user_with_order['user']
        order = user_with_order['order']
        
        # Set session first
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        # Login after session setup
        client.force_login(user)
        
        response = client.get(reverse('order_success'))
        
        assert response.status_code == 200
        assert 'order' in response.context
        assert response.context['order'].id == order.id
    
    def test_order_success_marks_order_as_viewed(self, client, user_with_order):
        """Test that viewing success page marks order as viewed."""
        user = user_with_order['user']
        order = user_with_order['order']
        
        assert not order.success_viewed
        
        # Set session first
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        # Login after session setup
        client.force_login(user)
        
        response = client.get(reverse('order_success'))
        
        order.refresh_from_db()
        assert order.success_viewed
        assert response.status_code == 200
    
    def test_order_success_without_session_order_id(self, client, user_with_order):
        """Test that missing order_id redirects to dashboard."""
        user = user_with_order['user']
        client.force_login(user)
        
        response = client.get(reverse('order_success'))
        
        assert response.status_code == 302
        assert response.url == reverse('participant_dashboard')
        
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert 'No recent order' in str(messages[0])
    
    def test_order_success_with_nonexistent_order(self, client, user_with_order):
        """Test that nonexistent order redirects to dashboard."""
        user = user_with_order['user']
        
        # Set session first
        session = client.session
        session['last_order_id'] = 99999  # Non-existent ID
        session.save()
        
        # Login after session setup
        client.force_login(user)
        
        response = client.get(reverse('order_success'))
        
        assert response.status_code == 302
        assert response.url == reverse('participant_dashboard')
        
        messages = list(get_messages(response.wsgi_request))
        assert len(messages) == 1
        assert 'Order not found' in str(messages[0])
    
    def test_order_success_with_another_users_order(self, client, user_with_order, db):
        """Test that users can't view other users' orders."""
        # Create another user
        other_user = UserFactory()
        ParticipantFactory(user=other_user)
        
        order = user_with_order['order']
        
        # Set session first
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        # Login after session setup
        client.force_login(other_user)
        
        response = client.get(reverse('order_success'))
        
        assert response.status_code == 302
        assert response.url == reverse('participant_dashboard')
    
    def test_order_success_handles_validation_error_gracefully(
        self, client, user_with_order
    ):
        """
        Test that validation errors on save don't prevent success page.
        This simulates the production error where balance validation fails.
        """
        user = user_with_order['user']
        order = user_with_order['order']
        
        # Set session first
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        # Login after session setup
        client.force_login(user)
        
        # Mock save to raise ValidationError
        with patch.object(Order, 'save') as mock_save:
            mock_save.side_effect = ValidationError("Food balance exceeded")
            
            response = client.get(reverse('order_success'))
            
            # Should still show success page
            assert response.status_code == 200
            assert 'order' in response.context
    
    def test_order_success_handles_unexpected_errors(
        self, client, user_with_order
    ):
        """Test that unexpected errors are caught and logged."""
        user = user_with_order['user']
        order = user_with_order['order']
        
        client.force_login(user)
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        # Mock save to raise unexpected error
        with patch.object(Order, 'save') as mock_save:
            mock_save.side_effect = RuntimeError("Database error")
            
            response = client.get(reverse('order_success'))
            
            # Should still show success page
            assert response.status_code == 200
            assert 'order' in response.context


@pytest.mark.django_db
class TestOrderSaveWithUpdateFields:
    """Test that Order.save() properly handles update_fields parameter."""
    
    def test_save_with_update_fields_skips_validation(self, user_with_order):
        """Test that save(update_fields=[...]) skips full_clean()."""
        order = user_with_order['order']
        account = user_with_order['account']
        
        # Set account balance to 0 to trigger validation if called
        account.base_balance = Decimal("0")
        account.save()
        
        # This should NOT raise ValidationError because update_fields skips validation
        order.success_viewed = True
        order.save(update_fields=['success_viewed'])
        
        order.refresh_from_db()
        assert order.success_viewed
    
    def test_save_without_update_fields_runs_validation(self, user_with_order):
        """Test that regular save() runs full validation."""
        order = user_with_order['order']
        account = user_with_order['account']
        
        # Set account balance to 0
        account.base_balance = Decimal("0")
        account.save()
        
        # Regular save should trigger validation and raise error
        order.success_viewed = True
        
        with pytest.raises(ValidationError) as exc_info:
            order.save()
        
        assert 'Food balance exceeded' in str(exc_info.value)


@pytest.mark.django_db
class TestOrderValidationEdgeCases:
    """Test edge cases in order validation logic."""
    
    def test_order_with_zero_balance_after_creation(self, user_with_order):
        """
        Test scenario where order is created with balance,
        but balance is consumed before viewing success page.
        """
        order = user_with_order['order']
        account = user_with_order['account']
        
        # Simulate balance being consumed (e.g., by another order)
        account.base_balance = Decimal("0")
        account.save()
        
        # Should be able to mark as viewed without triggering validation
        order.success_viewed = True
        order.save(update_fields=['success_viewed'])
        
        order.refresh_from_db()
        assert order.success_viewed
    
    def test_order_with_negative_balance_scenario(self, user_with_order):
        """Test order with account in negative balance."""
        order = user_with_order['order']
        account = user_with_order['account']
        
        # Set negative balance
        account.base_balance = Decimal("-50.00")
        account.save()
        
        # Should still be able to update specific fields
        order.status = 'completed'
        order.save(update_fields=['status'])
        
        order.refresh_from_db()
        assert order.status == 'completed'
    
    def test_multiple_orders_same_session(self, client, user_with_order, db):
        """Test that session properly tracks the most recent order."""
        user = user_with_order['user']
        account = user_with_order['account']
        
        # Create a second order
        order2 = Order.objects.create(
            user=user,
            account=account,
            status="confirmed"
        )
        
        client.force_login(user)
        session = client.session
        session['last_order_id'] = order2.id
        session.save()
        
        response = client.get(reverse('order_success'))
        
        assert response.status_code == 200
        assert response.context['order'].id == order2.id
    
    def test_order_validation_log_field_names(self, db):
        """Test that OrderValidationLog uses correct field names."""
        # This test verifies the fix for the 'message' vs 'error_message' bug
        user = UserFactory()
        participant = ParticipantFactory(user=user)
        account, _ = AccountBalance.objects.get_or_create(
            participant=participant
        )
        
        order = Order.objects.create(
            user=user,
            account=account,
            status="pending"
        )
        
        # Create log entry using the correct field name
        log = OrderValidationLog.objects.create(
            order=order,
            error_message="Test error message"
        )
        
        assert log.error_message == "Test error message"
        assert log.order == order
        
        # Verify field name (should not have 'message' field)
        field_names = [f.name for f in OrderValidationLog._meta.get_fields()]
        assert 'error_message' in field_names
        assert 'message' not in field_names


@pytest.mark.django_db
class TestOrderStatusTransitions:
    """Test order status transitions and validation."""
    
    def test_order_status_change_with_update_fields(self, user_with_order):
        """Test that status changes work with update_fields."""
        order = user_with_order['order']
        
        order.status = 'completed'
        order.save(update_fields=['status'])
        
        order.refresh_from_db()
        assert order.status == 'completed'
    
    def test_order_paid_flag_update(self, user_with_order):
        """Test that paid flag can be updated independently."""
        order = user_with_order['order']
        
        order.paid = True
        order.save(update_fields=['paid'])
        
        order.refresh_from_db()
        assert order.paid
    
    def test_order_multiple_field_update(self, user_with_order):
        """Test updating multiple fields with update_fields."""
        order = user_with_order['order']
        
        order.success_viewed = True
        order.paid = True
        order.save(update_fields=['success_viewed', 'paid'])
        
        order.refresh_from_db()
        assert order.success_viewed
        assert order.paid


@pytest.mark.django_db
class TestVoucherConsumptionEdgeCases:
    """Test edge cases with voucher consumption during order creation."""
    
    def test_order_success_after_voucher_consumption(
        self, client, user_with_order, db
    ):
        """
        Test that order success page works even when vouchers
        have reduced balance to zero.
        """
        from apps.voucher.models import Voucher
        
        user = user_with_order['user']
        order = user_with_order['order']
        account = user_with_order['account']
        
        # Create and consume voucher (voucher_amnt is calculated via property)
        voucher = Voucher.objects.create(
            account=account,
            voucher_type='grocery',
            state='consumed',
            active=False
        )
        
        # Set balance to 0 after voucher consumption
        account.base_balance = Decimal("0")
        account.save()
        
        client.force_login(user)
        session = client.session
        session['last_order_id'] = order.id
        session.save()
        
        response = client.get(reverse('order_success'))
        
        # Should still show success page
        assert response.status_code == 200
        assert response.context['order'].id == order.id
