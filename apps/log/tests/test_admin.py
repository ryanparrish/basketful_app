# apps/log/tests/test_admin.py
"""Tests for log admin configurations."""
import pytest
from unittest.mock import patch
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from apps.log.admin import EmailLogAdmin, OrderValidationLog
from apps.log.models import EmailLog
from apps.orders.tests.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class TestEmailLogAdmin:
    """Tests for EmailLogAdmin configuration."""

    def test_list_display_fields(self):
        """Verify list_display contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('id', 'user', 'email_type', 'subject', 'status', 'sent_at')
        assert admin.list_display == expected_fields

    def test_readonly_fields(self):
        """Verify readonly_fields contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('user', 'email_type', 'subject', 'status', 'error_message', 'sent_at', 'message_id')
        assert admin.readonly_fields == expected_fields

    def test_search_fields(self):
        """Verify search_fields contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('user__email', 'user__username', 'subject')
        assert admin.search_fields == expected_fields

    def test_list_filter(self):
        """Verify list_filter contains expected fields."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        
        expected_fields = ('status', 'email_type', 'sent_at')
        assert admin.list_filter == expected_fields

    def test_has_add_permission_returns_false(self):
        """Verify add permission is disabled."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')
        
        assert admin.has_add_permission(request) is False

    def test_has_delete_permission_returns_false(self):
        """Verify delete permission is disabled."""
        from apps.log.models import EmailType

        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')

        # Test without obj
        assert admin.has_delete_permission(request) is False

        # Test with obj
        user = UserFactory()
        email_type, _ = EmailType.objects.get_or_create(
            name='onboarding',
            defaults={
                'display_name': 'Onboarding Email',
                'subject': 'Welcome',
                'is_active': True
            }
        )
        email_log = EmailLog.objects.create(
            user=user,
            email_type=email_type
        )
        assert admin.has_delete_permission(request, email_log) is False

    def test_has_change_permission_returns_true(self):
        """Verify change permission returns False (logs are read-only)."""
        site = AdminSite()
        admin = EmailLogAdmin(EmailLog, site)
        request = RequestFactory().get('/')
        request.user = UserFactory(is_staff=True, is_superuser=True)
        
        # EmailLog should be read-only, so has_change_permission should return False
        assert admin.has_change_permission(request) is False


@pytest.mark.django_db
class TestOrderValidationLogAdmin:
    """Tests for OrderValidationLog admin registration."""

    def test_order_validation_log_is_registered(self):
        """Verify OrderValidationLog is registered with admin site."""
        from django.contrib import admin
        
        # Check if OrderValidationLog is registered
        assert OrderValidationLog in admin.site._registry
