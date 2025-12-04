# apps/log/tests/test_admin.py
"""Tests for log admin configurations."""
import pytest
from unittest.mock import patch
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.log.admin import EmailLogAdmin, OrderValidationLog
from apps.log.models import EmailLog
from apps.orders.tests.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestEmailLogAdmin:
    """Tests for EmailLogAdmin configuration."""

    def test_list_display_fields(self):
        """Verify list_display contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('id', 'user', 'sent_at', 'email_type')
        assert admin.list_display == expected_fields

    def test_readonly_fields(self):
        """Verify readonly_fields contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('user', 'email_type', 'sent_at')
        assert admin.readonly_fields == expected_fields

    def test_search_fields(self):
        """Verify search_fields contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('user', 'email_type', 'sent_at')
        assert admin.search_fields == expected_fields

    def test_list_filter(self):
        """Verify list_filter contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('user', 'email_type')
        assert admin.list_filter == expected_fields

    def test_has_add_permission_returns_false(self):
        """Verify add permission is disabled."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')
        
        assert admin.has_add_permission(request) is False

    def test_has_delete_permission_returns_false(self):
        """Verify delete permission is disabled."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')
        
        # Test without obj
        assert admin.has_delete_permission(request) is False
        
        # Test with obj
        user = UserFactory()
        email_log = EmailLog.objects.create(
            user=user,
            email_type='onboarding'
        )
        assert admin.has_delete_permission(request, email_log) is False

    @patch('apps.pantry.tasks.email.send_new_user_onboarding_email.delay')
    def test_has_change_permission_returns_true(self, mock_email):
        """Verify change permission is enabled (default behavior)."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')
        request.user = UserFactory(is_staff=True, is_superuser=True)
        
        # By default, has_change_permission should return True
        # This allows viewing/reading the logs
        assert admin.has_change_permission(request) is True


@pytest.mark.django_db
class TestOrderValidationLogAdmin:
    """Tests for OrderValidationLog admin registration."""

    def test_order_validation_log_is_registered(self):
        """Verify OrderValidationLog is registered with admin site."""
        from django.contrib import admin
        
        # Check if OrderValidationLog is registered
        assert OrderValidationLog in admin.site._registry
