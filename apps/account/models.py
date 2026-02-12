# account/models.py
"""Models for account-related data."""
from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from apps.lifeskills.models import Program, LifeskillsCoach
from .utils.balance_utils import (
    calculate_full_balance, 
    calculate_available_balance,
    calculate_hygiene_balance
)


class BaseModel(models.Model):
    """
    Abstract base class for models with an 'active' field.
    """
    active = models.BooleanField(default=True)
    objects = models.Manager()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)    

    class Meta:
        abstract = True


class UserProfile(BaseModel):
    """Extend the default User model with additional fields."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)

    def __str__(self) -> str:
        return getattr(self.user, "username", str(self.user))
    

class Participant(BaseModel):
    """Model representing a participant in the Life Skills program."""
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=False)  # required
    adults = models.PositiveIntegerField(default=1)
    children = models.PositiveIntegerField(default=0)
    diaper_count = models.PositiveIntegerField(
        default=0, help_text="Count of Children in Diapers or Pull-Ups"
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, null=True, blank=True
    )
    assigned_coach = models.ForeignKey(
        LifeskillsCoach, on_delete=models.CASCADE, related_name='customers',
        null=True, blank=True
    )
    create_user = models.BooleanField(
        default=False, help_text="If checked this will create a user account."
    )
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.CASCADE
    )
    allergy = models.CharField(
        max_length=100, default="None", blank=True, null=True
    )
    customer_number = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        help_text="Customer number format: C-XXX-D (e.g., C-BKM-7)"
    )

    def balances(self):
        """
        Return all balances related to this participant as a dict.
        Safe against missing AccountBalance.
        """
        try:
            account = AccountBalance.objects.get(participant=self)
        except models.ObjectDoesNotExist:
            return {
                "full_balance": 0,
                "available_balance": 0,
                "hygiene_balance": 0,
                "go_fresh_balance": 0,
            }
        return {
            "full_balance": account.full_balance,
            "available_balance": account.available_balance,
            "hygiene_balance": account.hygiene_balance,
            "go_fresh_balance": account.go_fresh_balance,
        }

    def __str__(self) -> str:
        return str(self.name)

    def household_size(self):
        """Calculate total household size."""
        return self.adults + self.children 

    def save(self, *args, **kwargs):
        # Generate customer number on first save with collision prevention
        if not self.customer_number:
            from .utils.warehouse_id import generate_unique_customer_number
            self.customer_number = generate_unique_customer_number(
                existing_numbers_queryset=Participant.objects.all()
            )
        self.full_clean()  # Optional if you want validation on every save
        super().save(*args, **kwargs)


class ActiveAccountBalanceManager(models.Manager):
    """Manager to return only active account balances."""
    def get_queryset(self):
        return super().get_queryset().filter(active=True)


# Class to represent account balance
class AccountBalance(BaseModel):
    """Model representing the account balance for a participant."""
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE)
    last_updated = models.DateTimeField(auto_now=True)
    base_balance = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    objects = models.Manager()
    active_accounts = ActiveAccountBalanceManager()

    @property
    def full_balance(self) -> Decimal:
        """Total balance of all active grocery vouchers."""
        return calculate_full_balance(self)

    @property
    def available_balance(self) -> Decimal:
        """
        Available balance using recent vouchers (pause logic handled at
        voucher level).
        """
        return calculate_available_balance(self)

    @property
    def hygiene_balance(self) -> Decimal:
        """Hygiene-specific balance (1/3 of full balance)."""
        return calculate_hygiene_balance(self)

    @property
    def go_fresh_balance(self) -> Decimal:
        """Go Fresh budget per order (based on household size)."""
        from .utils.balance_utils import calculate_go_fresh_balance
        return calculate_go_fresh_balance(self)

    def __str__(self) -> str:
        # Ensure a string is always returned (satisfies type checkers)
        return str(getattr(self.participant, "name", str(self.pk)))


class GoFreshSettings(models.Model):
    """
    Singleton model for Go Fresh budget configuration.
    
    Go Fresh operates as a per-order budget allowance based on household size.
    Unlike hygiene balance (which is a percentage of available balance), 
    Go Fresh budgets reset with each order and don't carry over.
    """
    small_household_budget = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        validators=[MinValueValidator(0.01)],
        help_text="Budget for households with 1-2 people (default: $10.00)"
    )
    medium_household_budget = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00,
        validators=[MinValueValidator(0.01)],
        help_text="Budget for households with 3-5 people (default: $20.00)"
    )
    large_household_budget = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=25.00,
        validators=[MinValueValidator(0.01)],
        help_text="Budget for households with 6+ people (default: $25.00)"
    )
    small_threshold = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Household size up to this number gets small budget (default: 2)"
    )
    large_threshold = models.PositiveIntegerField(
        default=6,
        validators=[MinValueValidator(1)],
        help_text="Household size at or above this gets large budget (default: 6)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Enable or disable Go Fresh budget feature"
    )
    
    class Meta:
        verbose_name = "Go Fresh Settings"
        verbose_name_plural = "Go Fresh Settings"
        permissions = [
            ("can_view_go_fresh_analytics", "Can view Go Fresh analytics dashboard")
        ]
    
    def clean(self):
        """Validate settings to prevent misconfiguration."""
        from django.core.exceptions import ValidationError
        errors = []
        
        if self.small_threshold >= self.large_threshold:
            errors.append(
                ValidationError(
                    "Small threshold must be less than large threshold. "
                    f"Currently: small={self.small_threshold}, large={self.large_threshold}"
                )
            )
        
        if self.small_household_budget <= 0:
            errors.append(ValidationError("Small household budget must be positive"))
        if self.medium_household_budget <= 0:
            errors.append(ValidationError("Medium household budget must be positive"))
        if self.large_household_budget <= 0:
            errors.append(ValidationError("Large household budget must be positive"))
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and GoFreshSettings.objects.exists():
            # Update existing instance instead of creating new one
            existing = GoFreshSettings.objects.first()
            existing.small_household_budget = self.small_household_budget
            existing.medium_household_budget = self.medium_household_budget
            existing.large_household_budget = self.large_household_budget
            existing.small_threshold = self.small_threshold
            existing.large_threshold = self.large_threshold
            existing.enabled = self.enabled
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'small_household_budget': Decimal('10.00'),
                'medium_household_budget': Decimal('20.00'),
                'large_household_budget': Decimal('25.00'),
                'small_threshold': 2,
                'large_threshold': 6,
                'enabled': True
            }
        )
        return obj
    
    def __str__(self) -> str:
        return f"Go Fresh Settings (Small: ${self.small_household_budget}, Medium: ${self.medium_household_budget}, Large: ${self.large_household_budget})"


class HygieneSettings(models.Model):
    """
    Singleton model for hygiene balance calculation settings.
    Controls what percentage of available balance is allocated for hygiene products.
    """
    hygiene_ratio = models.DecimalField(
        max_digits=30,
        decimal_places=28,
        default=Decimal('1') / Decimal('3'),
        help_text="Ratio of available balance allocated for hygiene (e.g., 0.333... = 1/3)"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Enable hygiene balance calculation"
    )

    class Meta:
        verbose_name = "Hygiene Settings"
        verbose_name_plural = "Hygiene Settings"

    def save(self, *args, **kwargs):
        # Enforce singleton pattern
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'hygiene_ratio': Decimal('1') / Decimal('3'),
                'enabled': True
            }
        )
        return obj

    def __str__(self) -> str:
        return f"Hygiene Settings (Ratio: {self.hygiene_ratio}, Enabled: {self.enabled})"


