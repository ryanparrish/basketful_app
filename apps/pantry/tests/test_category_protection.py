"""
Tests for category protection in admin.
"""
import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from django.test import RequestFactory
from apps.pantry.models import Category
from apps.pantry.admin import CategoryAdmin


@pytest.mark.django_db
class TestCategoryProtection:
    """Test category protection for Hygiene and Go Fresh."""
    
    @pytest.fixture
    def admin_user(self):
        """Create superuser for admin tests."""
        return User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='password123'
        )
    
    @pytest.fixture
    def request_factory(self):
        """Create request factory."""
        return RequestFactory()
    
    @pytest.fixture
    def category_admin(self):
        """Create CategoryAdmin instance."""
        return CategoryAdmin(Category, AdminSite())
    
    def test_hygiene_category_name_readonly(self, category_admin, admin_user, request_factory):
        """Hygiene category name field should be readonly."""
        hygiene_category = Category.objects.create(name="Hygiene")
        request = request_factory.get('/')
        request.user = admin_user
        
        readonly_fields = category_admin.get_readonly_fields(request, hygiene_category)
        
        assert 'name' in readonly_fields
    
    def test_go_fresh_category_name_readonly(self, category_admin, admin_user, request_factory):
        """Go Fresh category name field should be readonly."""
        go_fresh_category = Category.objects.create(name="Go Fresh")
        request = request_factory.get('/')
        request.user = admin_user
        
        readonly_fields = category_admin.get_readonly_fields(request, go_fresh_category)
        
        assert 'name' in readonly_fields
    
    def test_unprotected_category_name_editable(self, category_admin, admin_user, request_factory):
        """Unprotected category name should be editable."""
        regular_category = Category.objects.create(name="Groceries")
        request = request_factory.get('/')
        request.user = admin_user
        
        readonly_fields = category_admin.get_readonly_fields(request, regular_category)
        
        assert 'name' not in readonly_fields
    
    def test_case_insensitive_protection(self, category_admin, admin_user, request_factory):
        """Protection should be case-insensitive."""
        lowercase_hygiene = Category.objects.create(name="hygiene")
        mixed_case_go_fresh = Category.objects.create(name="Go FRESH")
        request = request_factory.get('/')
        request.user = admin_user
        
        hygiene_readonly = category_admin.get_readonly_fields(request, lowercase_hygiene)
        go_fresh_readonly = category_admin.get_readonly_fields(request, mixed_case_go_fresh)
        
        assert 'name' in hygiene_readonly
        assert 'name' in go_fresh_readonly
    
    def test_hygiene_category_cannot_be_deleted_via_permission(
        self, category_admin, admin_user, request_factory
    ):
        """Hygiene category should not have delete permission."""
        hygiene_category = Category.objects.create(name="Hygiene")
        request = request_factory.get('/')
        request.user = admin_user
        
        can_delete = category_admin.has_delete_permission(request, hygiene_category)
        
        assert can_delete is False
    
    def test_go_fresh_category_cannot_be_deleted_via_permission(
        self, category_admin, admin_user, request_factory
    ):
        """Go Fresh category should not have delete permission."""
        go_fresh_category = Category.objects.create(name="Go Fresh")
        request = request_factory.get('/')
        request.user = admin_user
        
        can_delete = category_admin.has_delete_permission(request, go_fresh_category)
        
        assert can_delete is False
    
    def test_unprotected_category_can_be_deleted(
        self, category_admin, admin_user, request_factory
    ):
        """Unprotected category should have delete permission."""
        regular_category = Category.objects.create(name="Beverages")
        request = request_factory.get('/')
        request.user = admin_user
        
        can_delete = category_admin.has_delete_permission(request, regular_category)
        
        assert can_delete is True
    
    def test_delete_model_raises_permission_denied_for_protected(
        self, category_admin, admin_user, request_factory
    ):
        """delete_model should raise PermissionDenied for protected categories."""
        hygiene_category = Category.objects.create(name="Hygiene")
        request = request_factory.get('/')
        request.user = admin_user
        
        with pytest.raises(PermissionDenied) as exc_info:
            category_admin.delete_model(request, hygiene_category)
        
        error_message = str(exc_info.value)
        assert "Cannot delete protected category" in error_message
        assert "Hygiene" in error_message
    
    def test_delete_model_works_for_unprotected(
        self, category_admin, admin_user, request_factory
    ):
        """delete_model should work normally for unprotected categories."""
        regular_category = Category.objects.create(name="Snacks")
        request = request_factory.get('/')
        request.user = admin_user
        
        # Should not raise exception
        category_admin.delete_model(request, regular_category)
        
        # Category should be deleted
        assert not Category.objects.filter(name="Snacks").exists()
    
    def test_lock_icon_displayed_for_protected_categories(
        self, category_admin, admin_user, request_factory
    ):
        """Protected categories should display with lock icon in list view."""
        hygiene_category = Category.objects.create(name="Hygiene")
        go_fresh_category = Category.objects.create(name="Go Fresh")
        regular_category = Category.objects.create(name="Pantry")
        
        # Check lock icon display
        hygiene_display = category_admin.name_with_lock(hygiene_category)
        go_fresh_display = category_admin.name_with_lock(go_fresh_category)
        regular_display = category_admin.name_with_lock(regular_category)
        
        assert "🔒" in hygiene_display
        assert "🔒" in go_fresh_display
        assert "🔒" not in regular_display
    
    def test_protected_categories_list_contains_both(self):
        """PROTECTED_CATEGORIES constant should contain both categories."""
        from apps.pantry.admin import PROTECTED_CATEGORIES
        
        assert 'hygiene' in PROTECTED_CATEGORIES
        assert 'go fresh' in PROTECTED_CATEGORIES
        assert len(PROTECTED_CATEGORIES) == 2


@pytest.mark.django_db
class TestCategoryProtectionIntegration:
    """Integration tests for category protection."""
    
    def test_protected_categories_survive_save_attempts(self):
        """Protected categories should exist and be protected after save."""
        # Create both protected categories
        hygiene = Category.objects.create(name="Hygiene")
        go_fresh = Category.objects.create(name="Go Fresh")
        
        # They should exist
        assert Category.objects.filter(name="Hygiene").exists()
        assert Category.objects.filter(name="Go Fresh").exists()
        
        # Verify they are protected (readonly name field)
        admin = CategoryAdmin(Category, AdminSite())
        request = RequestFactory().get('/')
        request.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        
        assert 'name' in admin.get_readonly_fields(request, hygiene)
        assert 'name' in admin.get_readonly_fields(request, go_fresh)
    
    def test_bulk_delete_protection(self):
        """Bulk delete operations should not delete protected categories."""
        # This test verifies that has_delete_permission prevents deletion
        # In actual admin usage, bulk actions check delete permissions
        hygiene = Category.objects.create(name="Hygiene")
        regular = Category.objects.create(name="Regular")
        
        admin = CategoryAdmin(Category, AdminSite())
        request = RequestFactory().get('/')
        request.user = User.objects.create_superuser('admin', 'admin@test.com', 'pass')
        
        # Hygiene should not be deletable
        assert admin.has_delete_permission(request, hygiene) is False
        
        # Regular should be deletable
        assert admin.has_delete_permission(request, regular) is True
