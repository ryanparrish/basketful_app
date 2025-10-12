# Standard library
from collections import defaultdict
from decimal import Decimal
from datetime import timedelta

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models,transaction
from django.db.models import (
    F, UniqueConstraint
)
from django.db.models.functions import ExtractWeek, ExtractYear
from django.utils.timezone import now
from django.utils import timezone

# Local app imports
from . import balance_utils, voucher_utils
from .queryset import program_pause_annotations
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django_ulid.models import ULIDField,default
from ulid import ULID
import logging

logger = logging.getLogger(__name__)

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
   
    def household_size(self):
        return self.adults + self.children 
     
    def save(self, *args, **kwargs):
        self.full_clean()  # Optional if you want validation on every save
        super().save(*args, **kwargs)

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
    id = ULIDField(primary_key=True, default=default, editable=False)
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey("AccountBalance", on_delete=models.PROTECT, related_name="orders")
    order_date = models.DateTimeField(auto_now_add=True)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    success_viewed = models.BooleanField(default=False)
    status_type = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("packing", "Packing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        help_text="The current status of the order."
    )
    paid = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def _orchestration(self):
        if not hasattr(self, "__orchestration"):
            logger.debug(f"Initializing OrderOrchestration for Order ID: {self.id}")
            from .utils.order_utils import OrderOrchestration
            self.__orchestration = OrderOrchestration(order=self)
        return self.__orchestration

    @property
    def total_price(self) -> Decimal:
        if not self.pk:  # Order not saved yet
            logger.debug("Order not saved yet, returning 0 total_price")
            return Decimal("0.00")

        from .utils.order_helper import OrderHelper
        total = OrderHelper.calculate_total_price(self)
        logger.debug(f"Total price calculated for Order ID {self.id}: {total}")
        return total

    def use_voucher(self, max_vouchers: int = 2, allow_partial: bool = False) -> bool:
        logger.debug(f"Applying vouchers for Order ID {self.id}")
        from .voucher_utils import apply_vouchers_to_order
        result = apply_vouchers_to_order(self, max_vouchers=max_vouchers)
        logger.debug(f"Vouchers applied result for Order ID {self.id}: {result}")
  
    def cancel(self):
        from .utils.order_utils import OrderOrchestration

        return OrderOrchestration(self).cancel()

    def clone(self, status="pending"):
        from .utils.order_utils import OrderOrchestration

        return OrderOrchestration(self).clone(status=status)
    
    def confirm(self):
        from .utils.order_utils import OrderOrchestration
        return OrderOrchestration(self).confirm()

    def edit(self):
        from .utils.order_utils import OrderOrchestration

        return OrderOrchestration(self).edit()
    @classmethod
    def generate_order_number(cls):
        today = now().strftime("%Y%m%d")  # YYYYMMDD
        prefix = "ORD"

        # Atomic increment to avoid race conditions
        with transaction.atomic():
            last_order = cls.objects.select_for_update().filter(
                order_number__startswith=f"{prefix}-{today}"
            ).order_by("order_number").last()

            if last_order:
                last_sequence = int(last_order.order_number.split("-")[-1])
                new_sequence = last_sequence + 1
            else:
                new_sequence = 1

            return f"{prefix}-{today}-{new_sequence:06d}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        skip_voucher = kwargs.pop("skip_voucher", False)
        is_new = self.pk is None
        prev_status = None

        if not is_new:
            prev_status = (
                Order.objects.filter(pk=self.pk)
                .values_list("status_type", flat=True)
                .first()
            )
            logger.debug(f"Previous status for Order ID {self.pk}: {prev_status}")

        logger.debug(f"Saving Order ID {self.pk} (new={is_new}, skip_voucher={skip_voucher})")
        super().save(*args, **kwargs)
        logger.debug(f"Order ID {self.pk} saved successfully.")

    def __str__(self):
        order_id = self.id or "(unsaved)"
        return f"Order #{order_id} - Status: {self.status_type}"

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
    state = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("applied", "Applied"), ("consumed", "Consumed")],
        default="pending",
        editable=False

    )
    program_pause_flag = models.BooleanField(default=False)
    multiplier = models.IntegerField(default=1,editable=False)
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

#Class to represent voucher payments
class OrderVoucher(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="applied_vouchers")
    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE)
    applied_amount = models.DecimalField(max_digits=10, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.order.id} - Voucher {self.voucher.id} (${self.applied_amount})"

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
