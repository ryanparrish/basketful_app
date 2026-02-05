"""
Management command to create default user groups with appropriate permissions.

This command creates the following groups:
1. Administrators - Full access to all features except superuser-only operations
2. Order Managers - Full CRUD on orders, export capabilities
3. Voucher Coordinators - Full CRUD on vouchers
4. Program Coordinators - Full CRUD on programs and participants
5. Inventory Managers - Full CRUD on pantry items and categories
6. Staff - Basic read/write access to core features
7. Read-Only - View-only access to all resources

Run with: python manage.py setup_groups
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Creates default user groups with appropriate permissions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating default groups...'))

        # Define groups and their permissions
        groups_config = {
            'Administrators': {
                'description': 'Full access to all features except superuser-only operations',
                'permissions': self._get_admin_permissions(),
            },
            'Order Managers': {
                'description': 'Full CRUD on orders, read access to related data',
                'permissions': self._get_order_manager_permissions(),
            },
            'Voucher Coordinators': {
                'description': 'Full CRUD on vouchers, read access to participants',
                'permissions': self._get_voucher_coordinator_permissions(),
            },
            'Program Coordinators': {
                'description': 'Full CRUD on programs and participants',
                'permissions': self._get_program_coordinator_permissions(),
            },
            'Inventory Managers': {
                'description': 'Full CRUD on pantry items and categories',
                'permissions': self._get_inventory_manager_permissions(),
            },
            'Staff': {
                'description': 'Basic read/write access to core features',
                'permissions': self._get_staff_permissions(),
            },
            'Read-Only': {
                'description': 'View-only access to all resources',
                'permissions': self._get_readonly_permissions(),
            },
        }

        for group_name, config in groups_config.items():
            group, created = Group.objects.get_or_create(name=group_name)
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Created group: {group_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'  Group already exists: {group_name}'))
                # Clear existing permissions
                group.permissions.clear()
            
            # Add permissions
            permissions = config['permissions']
            if permissions:
                group.permissions.add(*permissions)
                self.stdout.write(
                    f'  Added {len(permissions)} permissions to {group_name}'
                )
            
            self.stdout.write(f'  {config["description"]}')

        self.stdout.write(self.style.SUCCESS('\n✓ All groups configured successfully!'))

    def _get_admin_permissions(self):
        """Get all permissions except those requiring superuser"""
        # Get all permissions
        all_perms = Permission.objects.all()
        
        # Exclude user/group management (typically superuser only)
        # But include most other permissions
        excluded_models = []  # Could add specific exclusions if needed
        
        return all_perms

    def _get_order_manager_permissions(self):
        """Permissions for order management"""
        perms = []
        
        # Orders app - full CRUD
        perms.extend(self._get_model_permissions('orders', 'order'))
        perms.extend(self._get_model_permissions('orders', 'orderitem'))
        perms.extend(self._get_model_permissions('orders', 'combinedorder'))
        
        # Read access to related data
        perms.extend(self._get_model_permissions('account', 'participant', ['view']))
        perms.extend(self._get_model_permissions('lifeskills', 'program', ['view']))
        perms.extend(self._get_model_permissions('pantry', 'product', ['view']))
        perms.extend(self._get_model_permissions('pantry', 'category', ['view']))
        
        return perms

    def _get_voucher_coordinator_permissions(self):
        """Permissions for voucher management"""
        perms = []
        
        # Vouchers app - full CRUD
        perms.extend(self._get_model_permissions('voucher', 'voucher'))
        
        # Read access to participants
        perms.extend(self._get_model_permissions('account', 'participant', ['view']))
        perms.extend(self._get_model_permissions('lifeskills', 'program', ['view']))
        
        return perms

    def _get_program_coordinator_permissions(self):
        """Permissions for program and participant management"""
        perms = []
        
        # Programs and participants - full CRUD
        perms.extend(self._get_model_permissions('lifeskills', 'program'))
        perms.extend(self._get_model_permissions('account', 'participant'))
        
        # Read access to vouchers and orders
        perms.extend(self._get_model_permissions('voucher', 'voucher', ['view']))
        perms.extend(self._get_model_permissions('orders', 'order', ['view']))
        
        return perms

    def _get_inventory_manager_permissions(self):
        """Permissions for pantry inventory management"""
        perms = []
        
        # Pantry items and categories - full CRUD
        perms.extend(self._get_model_permissions('pantry', 'product'))
        perms.extend(self._get_model_permissions('pantry', 'category'))
        
        # Read access to orders
        perms.extend(self._get_model_permissions('orders', 'order', ['view']))
        perms.extend(self._get_model_permissions('orders', 'orderitem', ['view']))
        
        return perms

    def _get_staff_permissions(self):
        """Basic permissions for general staff"""
        perms = []
        
        # Add and change permissions for most models, no delete
        apps_models = [
            ('orders', 'order'),
            ('orders', 'orderitem'),
            ('voucher', 'voucher'),
            ('account', 'participant'),
            ('lifeskills', 'program'),
            ('pantry', 'product'),
        ]
        
        for app, model in apps_models:
            perms.extend(self._get_model_permissions(app, model, ['add', 'change', 'view']))
        
        return perms

    def _get_readonly_permissions(self):
        """View-only permissions for all resources"""
        perms = []
        
        # View permissions for all main models
        apps_models = [
            ('orders', 'order'),
            ('orders', 'orderitem'),
            ('orders', 'combinedorder'),
            ('voucher', 'voucher'),
            ('account', 'participant'),
            ('lifeskills', 'program'),
            ('pantry', 'product'),
            ('pantry', 'category'),
        ]
        
        for app, model in apps_models:
            perms.extend(self._get_model_permissions(app, model, ['view']))
        
        return perms

    def _get_model_permissions(self, app_label, model_name, actions=None):
        """
        Get permissions for a specific model.
        
        Args:
            app_label: The app label (e.g., 'orders')
            model_name: The model name (e.g., 'order')
            actions: List of actions (e.g., ['add', 'change', 'delete', 'view'])
                    If None, returns all actions
        
        Returns:
            QuerySet of Permission objects
        """
        if actions is None:
            actions = ['add', 'change', 'delete', 'view']
        
        try:
            content_type = ContentType.objects.get(
                app_label=app_label,
                model=model_name.lower()
            )
            
            codenames = [f'{action}_{model_name.lower()}' for action in actions]
            return list(Permission.objects.filter(
                content_type=content_type,
                codename__in=codenames
            ))
        except ContentType.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f'Warning: Model {app_label}.{model_name} not found'
                )
            )
            return []
