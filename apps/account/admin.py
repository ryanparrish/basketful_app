# account/admin.py
"""Admin configurations for account app."""
# Standard library
from decimal import Decimal
# Django imports
from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.apps import apps
# Local app imports
from .models import Participant
from .forms import CustomUserCreationForm, ParticipantAdminForm
from .models import UserProfile, AccountBalance, GoFreshSettings
from .utils.user_utils import _generate_admin_username, create_participant_user
from .utils.balance_utils import calculate_base_balance
from .tasks.email import send_password_reset_email, send_new_user_onboarding_email
from apps.pantry.utils.voucher_utils import setup_account_and_vouchers
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
        'customer_number',
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    readonly_fields = (
        'customer_number',
        'full_balance_display',
        'available_balance_display',
        'hygiene_balance_display',
        'get_base_balance',
    )
    actions = [
        'calculate_base_balance_action',
        'reset_password_and_send_email',
        'resend_onboarding_email',
        'resend_password_reset_email',
        'create_user_accounts',
        'create_user_accounts_silent',
        'print_customer_list',
    ]

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
    calculate_base_balance_action.short_description = (
        "Calculate and save base balance for selected participants"
    )

    def reset_password_and_send_email(self, request, queryset):
        """
        Reset password for selected participants and send password reset email.
        
        This action:
        1. Generates a random temporary password for each participant's user
        2. Sets the must_change_password flag
        3. Sends a password reset email to the user
        """
        reset_count = 0
        email_count = 0
        
        for participant in queryset:
            if not participant.user:
                continue
            
            user = participant.user
            
            # Generate a random temporary password
            temp_password = get_random_string(length=12)
            user.password = make_password(temp_password)
            user.save(update_fields=['password'])
            
            # Set must_change_password flag
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.must_change_password = True
            profile.save(update_fields=['must_change_password'])
            
            # Send password reset email (async)
            send_password_reset_email.delay(user.id)
            
            reset_count += 1
            email_count += 1
        
        self.message_user(
            request,
            (
                f"Password reset for {reset_count} participant(s). "
                f"{email_count} password reset email(s) queued."
            )
        )
    reset_password_and_send_email.short_description = (
        "Reset password and send reset email"
    )

    def resend_onboarding_email(self, request, queryset):
        """
        Resend onboarding email to selected participants.
        Uses force=True to bypass the duplicate check.
        """
        sent_count = 0
        skipped_no_user = 0
        skipped_no_email = 0
        
        for participant in queryset:
            if not participant.user:
                skipped_no_user += 1
                continue
            
            if not participant.user.email:
                skipped_no_email += 1
                continue
            
            send_new_user_onboarding_email.delay(participant.user.id, force=True)
            sent_count += 1
        
        messages = []
        if sent_count:
            messages.append(f"Queued {sent_count} onboarding email(s). Check Log > Email Logs for delivery status.")
        if skipped_no_user:
            messages.append(f"Skipped {skipped_no_user} (no user account).")
        if skipped_no_email:
            messages.append(f"Skipped {skipped_no_email} (no email address).")
        
        self.message_user(request, " ".join(messages) or "No participants selected.")
    resend_onboarding_email.short_description = "Resend onboarding email"

    def resend_password_reset_email(self, request, queryset):
        """
        Resend password reset email to selected participants.
        Uses force=True to bypass the duplicate check.
        """
        sent_count = 0
        skipped_no_user = 0
        skipped_no_email = 0
        
        for participant in queryset:
            if not participant.user:
                skipped_no_user += 1
                continue
            
            if not participant.user.email:
                skipped_no_email += 1
                continue
            
            send_password_reset_email.delay(participant.user.id, force=True)
            sent_count += 1
        
        messages = []
        if sent_count:
            messages.append(f"Queued {sent_count} password reset email(s). Check Log > Email Logs for delivery status.")
        if skipped_no_user:
            messages.append(f"Skipped {skipped_no_user} (no user account).")
        if skipped_no_email:
            messages.append(f"Skipped {skipped_no_email} (no email address).")
        
        self.message_user(request, " ".join(messages) or "No participants selected.")
    resend_password_reset_email.short_description = "Resend password reset email"

    def _create_user_for_participant(self, participant, send_email=True):
        """
        Create a user account for a participant without one.
        
        Args:
            participant: The Participant instance
            send_email: Whether to send the onboarding email
            
        Returns:
            tuple: (success: bool, reason: str)
                - (True, 'created') if user was created
                - (False, 'has_user') if participant already has a user
                - (False, 'no_email') if participant has no email address
        """
        # Skip if already has a user
        if participant.user:
            return (False, 'has_user')
        
        # Skip if no email (required for user account)
        if not participant.email:
            return (False, 'no_email')
        
        # Create user account
        user = create_participant_user(
            first_name=participant.name,
            email=participant.email,
            participant_name=participant.name,
        )
        participant.user = user
        participant.save(update_fields=['user'])
        
        # Ensure UserProfile exists
        UserProfile.objects.get_or_create(user=user)
        
        # Setup account and vouchers (idempotent)
        setup_account_and_vouchers(participant)
        
        # Send onboarding email if requested
        if send_email:
            send_new_user_onboarding_email.delay(user_id=user.id)
        
        return (True, 'created')

    def create_user_accounts(self, request, queryset):
        """
        Create user accounts for selected participants who don't have one.
        Sends onboarding email to newly created users.
        """
        created_count = 0
        skipped_has_user = 0
        skipped_no_email = 0
        
        for participant in queryset:
            success, reason = self._create_user_for_participant(participant, send_email=True)
            if success:
                created_count += 1
            elif reason == 'has_user':
                skipped_has_user += 1
            elif reason == 'no_email':
                skipped_no_email += 1
        
        messages = []
        if created_count:
            messages.append(f"Created {created_count} user account(s). Onboarding email(s) queued.")
        if skipped_has_user:
            messages.append(f"Skipped {skipped_has_user} (already have user).")
        if skipped_no_email:
            messages.append(f"Skipped {skipped_no_email} (no email address).")
        
        self.message_user(request, " ".join(messages) or "No participants selected.")
    create_user_accounts.short_description = "Create user accounts"

    def create_user_accounts_silent(self, request, queryset):
        """
        Create user accounts for selected participants who don't have one.
        Does NOT send onboarding email (silent creation).
        """
        created_count = 0
        skipped_has_user = 0
        skipped_no_email = 0
        
        for participant in queryset:
            success, reason = self._create_user_for_participant(participant, send_email=False)
            if success:
                created_count += 1
            elif reason == 'has_user':
                skipped_has_user += 1
            elif reason == 'no_email':
                skipped_no_email += 1
        
        messages = []
        if created_count:
            messages.append(f"Created {created_count} user account(s) (no email sent).")
        if skipped_has_user:
            messages.append(f"Skipped {skipped_has_user} (already have user).")
        if skipped_no_email:
            messages.append(f"Skipped {skipped_no_email} (no email address).")
        
        self.message_user(request, " ".join(messages) or "No participants selected.")
    create_user_accounts_silent.short_description = "Create user accounts (silent - no email)"

    def print_customer_list(self, request, queryset):
        """
        Print a list of selected customers grouped by program with customer numbers.
        """
        from django.shortcuts import redirect
        from django.urls import reverse
        
        # Store selected participant IDs in session
        participant_ids = list(queryset.values_list('id', flat=True))
        request.session['print_customer_ids'] = participant_ids
        
        # Redirect to print view
        return redirect(reverse('print_customer_list'))
    print_customer_list.short_description = "Print customer list"


@admin.register(GoFreshSettings)
class GoFreshSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Go Fresh Settings (singleton)."""
    
    list_display = ['get_budget_summary', 'enabled']
    
    fieldsets = (
        ('Household Size Thresholds', {
            'fields': ('small_threshold', 'large_threshold'),
            'description': (
                '<p><strong>Define household size ranges:</strong></p>'
                '<ul>'
                '<li><strong>Small threshold:</strong> Household sizes up to this number '
                'receive the small budget</li>'
                '<li><strong>Large threshold:</strong> Household sizes at or above this number '
                'receive the large budget</li>'
                '<li>Sizes between these thresholds receive the medium budget</li>'
                '</ul>'
            )
        }),
        ('Budget Amounts', {
            'fields': ('small_household_budget', 'medium_household_budget', 'large_household_budget'),
            'description': (
                '<p>⚠️ <strong>Per-Order Budget:</strong> These amounts apply to EACH order. '
                'Participants receive a fresh Go Fresh budget with every new order. '
                'Budget does not carry over between orders.</p>'
                '<p><strong>Impact Warning:</strong> Changing these values affects all future orders immediately.</p>'
            )
        }),
        ('Feature Control', {
            'fields': ('enabled',),
            'description': 'Enable or disable the Go Fresh budget feature system-wide.'
        }),
    )
    
    def get_budget_summary(self, obj):
        """Display budget configuration summary."""
        if obj:
            return (
                f"Small(1-{obj.small_threshold}): ${obj.small_household_budget} | "
                f"Medium({obj.small_threshold + 1}-{obj.large_threshold - 1}): ${obj.medium_household_budget} | "
                f"Large({obj.large_threshold}+): ${obj.large_household_budget}"
            )
        return "No settings configured"
    
    get_budget_summary.short_description = 'Budget Configuration'
    
    def has_add_permission(self, request):
        """Prevent adding multiple instances (singleton)."""
        return not GoFreshSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the settings."""
        return False


