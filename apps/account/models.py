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
            }
        return {
            "full_balance": account.full_balance,
            "available_balance": account.available_balance,
            "hygiene_balance": account.hygiene_balance,
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

    def __str__(self) -> str:
        # Ensure a string is always returned (satisfies type checkers)
        return str(getattr(self.participant, "name", str(self.pk)))

