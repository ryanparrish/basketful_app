# Standard library
from collections import defaultdict
from decimal import Decimal
from datetime import timedelta

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import (
    F, UniqueConstraint
)
from django.db.models.functions import ExtractWeek, ExtractYear
from django.utils.timezone import now

# Local app imports
from . import balance_utils, voucher_utils
from .order_utils import calculate_total_price, OrderUtils
from .queryset import program_pause_annotations
from .voucher_utils import apply_vouchers
from .order_utils import OrderUtils, get_order_print_context
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Categories"


class Subcategory(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')

    def __str__(self):
        return f"{self.category.name} > {self.name}"
# Class to represent a product in inventory
class Product(models.Model):
    is_meat = models.BooleanField(default=False)
    weight_lbs = models.DecimalField(max_digits=4, decimal_places=2, default=0)  # e.g., 1.00 for beef, 2.00 for chicken
    category = models.ForeignKey(Category,on_delete=models.CASCADE, related_name="product",)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    quantity_in_stock = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    active = models.BooleanField(default=True)
    @staticmethod
    def get_limit_for_product(product):
        subcat_limit = (
            ProductManager.objects
            .filter(subcategory=product.subcategory)
            .order_by('limit')
            .first()
        )
        cat_limit = (
            ProductManager.objects
            .filter(category=product.category, subcategory__isnull=True)
            .order_by('limit')
            .first()
        )

        limits = []
        if subcat_limit:
            limits.append(subcat_limit.limit)
        if cat_limit:
            limits.append(cat_limit.limit)

        return min(limits) if limits else None

    def __str__(self):
        return self.name
    
class ProductManager(models.Model):
    name= models.CharField(max_length=100)
    category = models.OneToOneField(
    Category,
    on_delete=models.CASCADE,
    related_name="product_manager", 
    help_text="If category is selected, limit will be enforced at the category level."
    )
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE, help_text="If Sub-Category is selected limit will be applied at the subcategory level", null=True, blank=True) 
    notes = models.TextField(blank=True, null=True)
    limit = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of products allowed in this category per order."
    )
    limit_scope = models.CharField(
        max_length=20,
        choices=[
            ('per_adult', 'Per Adult'),
            ('per_child', 'Per Child'),
            ('per_infant', 'Per Infant'),
            ('per_household', 'Per Household'),
            ('per_order', 'Per Order'),
        ],
        default='per_household',
        null=True,
        blank=True,
        help_text="Scope of the limit: Adult, Child, Infant or Household."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
#Class to represent a calender of when there is no class 

class ProgramPauseQuerySet(models.QuerySet):
    def with_annotations(self):
        return program_pause_annotations(self)

    def active(self):
        return self.with_annotations().filter(is_active_gate=True)



class ProgramPause(models.Model):
    pause_start = models.DateTimeField()
    pause_end = models.DateTimeField()
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------------------
    # Core pause calculation (dynamic)
    # -------------------------------
    from django.utils.timezone import now

    def _calculate_pause_status(self) -> tuple[int, str]:
        """
        Determine pause multiplier and message based on start date and duration.

        Rules:
            - Only orders placed 14–11 days before pause start are affected
            - Short pause (<14 days) → multiplier 2
            - Extended pause (>=14 days) → multiplier 3
            - Orders outside this window → multiplier 1
        """
        if not self.pause_start or not self.pause_end:
            return 1, f"{self.reason or 'Unnamed'} not affecting this order"

        today = now()  # datetime.datetime
        days_until_start = (self.pause_start - today).days  # now both are datetime
        duration = (self.pause_end - self.pause_start).days + 1

        if 11 <= days_until_start <= 14:
            if duration >= 14:
                return 3, f"{self.reason or 'Unnamed'} Extended pause affecting this order (duration {duration} days)"
            elif duration >= 1:
                return 2, f"{self.reason or 'Unnamed'} Short pause affecting this order (duration {duration} days)"

        return 1, f"{self.reason or 'Unnamed'} not affecting this order"

    @property
    def multiplier(self) -> int:
        multiplier, _ = self._calculate_pause_status()
        return multiplier

    @property
    def is_active_gate(self) -> bool:
        """Pause is active if the multiplier is greater than 1."""
        return self.multiplier > 1

    # -------------------------------
    # Validations
    # -------------------------------


def clean(self):
    """Prevent overlapping pauses and invalid dates."""
    super().clean()  # call first for base validation

    now_dt = timezone.now()  # current datetime

    if self.pause_start and self.pause_end:
        if self.pause_end < self.pause_start:
            raise ValidationError("End datetime cannot be earlier than start datetime.")

        # Minimum 11 days out (using datetime)
        min_start_dt = now_dt + timedelta(days=11)
        if self.pause_start < min_start_dt:
            raise ValidationError("Pause start must be at least 11 days from now.")

        # Maximum 14-day pause
        if (self.pause_end - self.pause_start) > timedelta(days=14):
            raise ValidationError("Program pause cannot be longer than 14 days.")

        # Prevent overlapping pauses
        overlap_exists = ProgramPause.objects.exclude(pk=self.pk).filter(
            pause_start__lt=self.pause_end,
            pause_end__gt=self.pause_start,
        ).exists()
        if overlap_exists:
            raise ValidationError("Another program pause already exists in this period.")

# Class to represent a Life Skills coach
class LifeSkillsCoach (models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='coaches/', blank=True, null=True)
    def __str__(self):
        return self.name
   # Class to represent a Life Skills program
class Program(models.Model):
    name= models.CharField(max_length=100)
    meeting_time = models.TimeField()
    MeetingDay = models.CharField(
    blank=False,
    choices=[
            ('monday' ,'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
        ]      
    )
    meeting_address= models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name
# Class to represent a participant in the program
class Participant(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=False)  # required
    adults = models.PositiveIntegerField(default=1)
    children = models.PositiveIntegerField(default=0)
    diaper_count = models.PositiveIntegerField(
        default=0, help_text="Count of Children in Diapers or Pull-Ups"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, null=True, blank=True
    )
    assigned_coach = models.ForeignKey(
        LifeSkillsCoach, on_delete=models.CASCADE, related_name='customers', null=True, blank=True
    )
    create_user = models.BooleanField(
        default=False, help_text="If checked this will create a user account."
    )
    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)
    allergy = models.CharField(max_length=100, default="None", blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Optional: full_clean for validation on every save
        self.full_clean()
        super().save(*args, **kwargs)

    def balances(self):
        """
        Return all balances related to this participant as a dict.
        Safe against missing AccountBalance.
        """
        try:
            account = self.accountbalance
        except AccountBalance.DoesNotExist:
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
 
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.full_clean()  # Optional if you want validation on every save
        super().save(*args, **kwargs)
    def household_size(self):
        return self.adults + self.children 
# Class to represent account balance
class AccountBalance(models.Model):
    participant = models.OneToOneField(Participant, on_delete=models.CASCADE)
    last_updated = models.DateTimeField(auto_now=True)
    base_balance = models.DecimalField(max_digits=4,decimal_places=1,default=0, validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
   # Assuming this is inside your AccountBalance model

    @property
    def full_balance(self) -> Decimal:
        """Total balance of all active grocery vouchers."""
        return balance_utils.calculate_full_balance(self)

    @property
    def available_balance(self) -> Decimal:
        """Available balance using recent vouchers (pause logic handled at voucher level)."""
        return balance_utils.calculate_available_balance(self)

    @property
    def hygiene_balance(self) -> Decimal:
        """Hygiene-specific balance (1/3 of full balance)."""
        return balance_utils.calculate_hygiene_balance(self)

    def __str__(self) -> str:
        return getattr(self.participant, "name", str(self.pk))


class Order(models.Model):
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey("AccountBalance", on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateTimeField(auto_now_add=True)
    status_type = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('packing', 'Packing'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        null=False,
        help_text="The current status of the order. Options are: Pending New-Unpaid, Confirmed Paid, Packing, Complete Packed, or Cancelled."
    )

    paid = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # -------------------------------
    # Utility properties
    # -------------------------------
    @property
    def _order_utils(self):
        return OrderUtils(self)

    @property
    def total_price(self) -> Decimal:
        return calculate_total_price(self)

    # -------------------------------
    # Validation
    # -------------------------------
    @staticmethod
    def validate_items_static(items, participant, account):
        """Validate a list of OrderItemData for a participant and account."""
        validate_order_items(items, participant, account)

    def validate_items(self, items):
        participant = getattr(self.account, "participant", None)
        if participant:
            self.validate_items_static(items, participant, self.account)

    # -------------------------------
    # Order actions
    # -------------------------------
    def confirm(self):
        return self._order_utils.confirm()

    def cancel(self):
        return self._order_utils.cancel()

    def clone(self, status="pending"):
        return self._order_utils.clone(status=status)

    def edit(self):
        return self._order_utils.edit()

    # -------------------------------
    # Voucher logic
    # -------------------------------
    def use_voucher(self, max_vouchers: int = 2) -> bool:
        """
        Apply eligible grocery vouchers to this order and mark as paid.
        Returns True if any voucher was applied, False otherwise.
        """
        from . import voucher_utils
        return voucher_utils.apply_vouchers(self, max_vouchers=max_vouchers)

    # -------------------------------
    # Override save to apply vouchers when confirmed
    # -------------------------------
    def save(self, *args, **kwargs):
        # Custom kwarg to prevent recursion when apply_vouchers calls save()
        skip_voucher = kwargs.pop("skip_voucher", False)

        is_new = self.pk is None
        prev_status = None

        if not is_new:
            prev_status = (
                Order.objects.filter(pk=self.pk)
                .values_list("status_type", flat=True)
                .first()
            )

        super().save(*args, **kwargs)  # normal save

        # Only apply vouchers if:
        # - not skipping
        # - status is confirmed
        # - this is a new order OR status just changed to confirmed
        if not skip_voucher:
            if self.status_type == "confirmed" and (is_new or prev_status != "confirmed"):
                applied = self.use_voucher()
                if applied and not self.paid:
                    # Ensure paid is persisted
                    self.paid = True
                    super().save(update_fields=["paid"])

    # -------------------------------
    # Print / context utilities
    # -------------------------------
    def print_context(self):
        return get_order_print_context(self)

class OrderItem(models.Model):
    order = models.ForeignKey(
        'Order',
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    # Current product price reference (useful for comparisons/reports)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    # Historical price locked at time of order
    price_at_order = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Only set once (don’t overwrite if it already exists)
        if self.price_at_order is None and self.product_id:
            self.price_at_order = self.product.price
        super().save(*args, **kwargs)

    def total_price(self):
        return self.quantity * self.price
    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order #{self.order.id})"
    def save(self, *args, **kwargs):
        if self.product:
            self.price = self.product.price
        super().save(*args, **kwargs)

class CombinedOrder(models.Model):
    program = models.ForeignKey(
        'Program',
        on_delete=models.CASCADE,
        related_name='combined_orders'
    )
    orders = models.ManyToManyField(
        'Order',
        related_name='combined_orders',
        blank=True
    )
    packed_by = models.ForeignKey(
        'OrderPacker',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='combined_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    summarized_data = models.JSONField(default=dict, blank=True)
    is_parent = models.BooleanField(default=False)

    def summarized_items_by_category(self):
        summary = defaultdict(lambda: defaultdict(int))
        orders_qs = self.orders.select_related(
            'account__participant__program'
        ).prefetch_related(
            'items__product__category'
        )
        for order in orders_qs:
            participant = getattr(order.account, 'participant', None)
            if not participant or participant.program != self.program:
                continue
            for item in order.items.all():
                product = item.product
                category_name = product.category.name if product.category else "Uncategorized"
                summary[category_name][product.name] += item.quantity
        return summary

    class Meta:
        constraints = [
            UniqueConstraint(
                F("program"),
                ExtractYear("created_at"),
                ExtractWeek("created_at"),
                name="unique_program_per_week",
            )
        ]

    def __str__(self):
        return f"{self.program.name} Combined Order ({self.created_at.strftime('%Y-%m-%d')})"

# Class to represent who packed the order
class OrderPacker(models.Model):
    name= models.CharField(max_length=100)
    programs = models.ManyToManyField('Program', related_name='packers', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return self.name

#Class to represent voucher settings
class VoucherSetting(models.Model):
    adult_amount = models.DecimalField(max_digits=3, decimal_places=1, default=20, validators=[MinValueValidator(0)])
    child_amount = models.DecimalField(max_digits=3, decimal_places=1, default=12.5,validators=[MinValueValidator(0)])
    infant_modifier = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Voucher Setting (Updated: {self.updated_at.strftime('%Y-%m-%d')})"
    def save(self, *args, **kwargs):
        if self.active:
            VoucherSetting.objects.exclude(id=self.id).update(active=False)
        super().save(*args, **kwargs)
    # Ensure only one active setting at a time
    class Meta:
        verbose_name_plural = "Voucher Settings"

#Class to represent voucher payments
class Voucher(models.Model):
    account= models.ForeignKey(AccountBalance, on_delete=models.CASCADE, related_name='vouchers')
    active = models.BooleanField(default=True)
    voucher_type = models.CharField(
        blank=False,
        choices=[
            ('life', 'Life'),
            ('grocery', 'Grocery'),
        ],
        default='grocery',
        max_length=20,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, default=" ")
    program_pause_flag = models.BooleanField(default=False)
    multiplier = models.IntegerField(default=1)
    @property
    def voucher_amnt(self) -> Decimal:
        """
        Compute the redeemable amount for this voucher.
        Uses the refactored logic in voucher_utils.
        """
        return voucher_utils.calculate_voucher_amount(self)
    
    def __str__(self):
        return f"Voucher ({self.pk})"
  
User = get_user_model()

class EmailLog(models.Model):
    EMAIL_TYPE_CHOICES = [
        ("onboarding", "Onboarding"),
        ("password_reset", "Password Reset"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=50, choices=EMAIL_TYPE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=255, blank=True, null=True)  # optional Mailgun ID
    status = models.CharField(max_length=50, default="sent")  # sent, delivered, failed, opened

    class Meta:
        unique_together = ("user", "email_type")  # prevents duplicate entries per type

# -----------------------
# Abstract base class
# -----------------------
class BaseLog(models.Model):
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

    LOG_TYPE_CHOICES = [
        (INFO, 'Info'),
        (WARNING, 'Warning'),
        (ERROR, 'Error'),
    ]

    participant = models.ForeignKey(
        "Participant",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    order = models.ForeignKey(
        "Order",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    message = models.TextField()
    log_type = models.CharField(max_length=10, choices=LOG_TYPE_CHOICES, default=INFO)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        target = f"Order {self.order.id}" if self.order else "General"
        return f"{target} [{self.log_type}]: {self.message[:50]}"

# -----------------------
# Concrete log models
# -----------------------
class VoucherLog(BaseLog):
    voucher = models.ForeignKey(
        "Voucher",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="logs"
    )
    balance_before = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    validated_at = models.DateTimeField(auto_now_add=True)  # when voucher was validated/consumed

    def __str__(self):
        target = f"Voucher {self.voucher.id}" if self.voucher else super().__str__()
        return f"{target} [{self.log_type}]: {self.message[:50]}"

class OrderValidationLog(BaseLog):
    product = models.ForeignKey(
        "Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    validated_at = models.DateTimeField(auto_now_add=True)  # when validation occurred

    def __str__(self):
        return f"{self.validated_at} — {self.participant or 'Unknown'}: {self.message}"
