# account/admin.py
"""Admin configurations for account app."""
# Standard library
from decimal import Decimal
# Django imports
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.apps import apps
# Local app imports
from .models import Participant
from .forms import CustomUserCreationForm, ParticipantAdminForm
from .models import UserProfile, AccountBalance
from .utils.user_utils import _generate_admin_username
from .utils.balance_utils import calculate_base_balance
User = get_user_model()

# Lazily load the Product model to avoid circular import issues
Product = apps.get_model('pantry', 'Product')

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # If not registered yet, ignore 


@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    """Custom admin for User model with dynamic fieldsets."""
    add_form = CustomUserCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'is_staff'),
        }),
    )

    # Default fieldsets for editing users
    base_fieldsets = (
        (None, {
            'fields': ('email', 'first_name', 'last_name', 'is_staff', 'is_active'),
        }),
    )

    staff_extra_fieldsets = (
        ('Permissions', {
            'fields': ('groups', 'user_permissions', 'is_superuser'),
        }),
    )

    def get_fieldsets(self, request, obj=None):
        """
        Show additional fields if the user is staff.
        """
        if obj is None:
            return self.add_fieldsets

        fieldsets = list(self.base_fieldsets)
        if obj.is_staff:
            fieldsets += list(self.staff_extra_fieldsets)
        return fieldsets

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.add_form
        return super().get_form(request, obj, **kwargs)
    
    def save_model(self, request, obj, form, change):
        is_new = obj.pk is None

        if is_new:
            # Generate a username based on first+last name
            base_name = f"{obj.first_name}_{obj.last_name}".strip() or "user"
            for candidate in _generate_admin_username(base_name):
                if not User.objects.filter(username=candidate).exists():
                    obj.username = candidate
                    break

        super().save_model(request, obj, form, change)

        if is_new:
            # Ensure profile exists and set must_change_password
            profile, _ = UserProfile.objects.get_or_create(user=obj)
            profile.must_change_password = True
            profile.save(update_fields=["must_change_password"])


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    """Admin for Participant with balance displays and actions."""
    form = ParticipantAdminForm
    list_display = (
        'name',
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    readonly_fields = (
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    actions = ['calculate_base_balance_action']

    def full_balance_display(self, obj):
        """Display the full balance of the participant."""
        balance = obj.balances().get('full_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    full_balance_display.short_description = "Full Balance"

    def available_balance_display(self, obj):
        """Display the available balance of the participant."""
        balance = obj.balances().get('available_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    available_balance_display.short_description = "Available Balance"

    def hygiene_balance_display(self, obj):
        """Display the hygiene balance of the participant."""
        balance = obj.balances().get('hygiene_balance', 0)
        return f"${balance:.2f}" if balance else "No Balance"
    hygiene_balance_display.short_description = "Hygiene Balance"

    def get_base_balance(self, obj):
        """Display the base balance from AccountBalance."""
        if hasattr(obj, 'accountbalance'):
            return f"${obj.accountbalance.base_balance:,.2f}"
        return Decimal(0)
    get_base_balance.short_description = "Base Balance"

    def calculate_base_balance_action(self, request, queryset):
        """Calculate and save base balance for selected participants."""
        updated_count = 0
        for participant in queryset:
            base = calculate_base_balance(participant)
            # Ensure AccountBalance exists
            account_balance, created = AccountBalance.objects.get_or_create(
                participant=participant
            )
            account_balance.base_balance = base
            account_balance.save()
            updated_count += 1

        self.message_user(
            request,
            (
                f"Base balance calculated and saved for {updated_count} "
                "participants."
            )
        )
    calculate_base_balance_action.short_description = "Calculate and save base balance for selected participants"

