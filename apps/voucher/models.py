"""Voucher models and utilities."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
import logging
from apps.voucher.utils import calculate_voucher_amount
from apps.orders.models import Order

logger = logging.getLogger(__name__)
User = get_user_model()


# ============================================================
# Models
# ============================================================

class VoucherSetting(models.Model):
    """Model representing voucher settings."""
    
    objects = models.Manager()
    adult_amount = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=20,
        validators=[MinValueValidator(0)]
    )
    child_amount = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=12.5,
        validators=[MinValueValidator(0)]
    )
    infant_modifier = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0)]
    )
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Voucher Settings"

    def __str__(self):
        updated_at_value = self.updated_at
        if hasattr(updated_at_value, "strftime"):
            formatted_date = updated_at_value.strftime('%Y-%m-%d')
        else:
            formatted_date = str(updated_at_value)
        return f"Voucher Setting (Updated: {formatted_date})"

    def save(self, *args, **kwargs):
        """Ensure only one active setting at a time."""
        if self.active:
            VoucherSetting.objects.exclude(id=self.id).update(active=False)
        super().save(*args, **kwargs)


class ActiveVouchersManager(models.Manager):
    """Manager to return only active vouchers."""
    def get_queryset(self):
        return super().get_queryset().filter(active=True)


class Voucher(models.Model):
    """Model representing a voucher."""
    
    VOUCHER_TYPE_CHOICES = [
        ('life', 'Life'),
        ('grocery', 'Grocery'),
    ]
    
    STATE_CHOICES = [
        ("pending", "Pending"),
        ("applied", "Applied"),
        ("consumed", "Consumed"),
        ("expired", "Expired"),
    ]
    
    # State constants
    PENDING = "pending"
    APPLIED = "applied"
    CONSUMED = "consumed"
    EXPIRED = "expired"

    account = models.ForeignKey(
        'account.AccountBalance',
        on_delete=models.CASCADE,
        related_name='vouchers'
    )
    active = models.BooleanField(default=True)
    voucher_type = models.CharField(
        max_length=20,
        choices=VOUCHER_TYPE_CHOICES,
        default='grocery',
        blank=False,
    )
    state = models.CharField(
        max_length=20,
        choices=STATE_CHOICES,
        default="pending",
        editable=False
    )
    program_pause_flag = models.BooleanField(default=False)
    multiplier = models.IntegerField(default=1, editable=False)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    active_vouchers = ActiveVouchersManager()

    def _get_active_vouchers(self, account_balance):
        """Return all active (applied) vouchers for the given account."""
        return account_balance.vouchers.filter(state="applied")

    def _validate_voucher_presence(self, account_balance, active_vouchers):
        """Raise if no active vouchers are available."""
        if not active_vouchers.exists():
            participant = getattr(account_balance, "participant", None)
            raise ValidationError(
                f"[{participant}] Cannot confirm order: No vouchers applied to account."
            )

    def _calculate_total_voucher_balance(self, active_vouchers):
        """Calculate total available voucher balance."""
        return sum(voucher.voucher_amnt for voucher in active_vouchers)

    def _validate_voucher_balance(
        self, account_balance, order_total, total_voucher_balance
    ):
        """Validate that voucher balance covers order total."""
        logger.debug(
            "[Voucher Validator] Order total: %s, Total voucher balance: %s",
            order_total,
            total_voucher_balance,
        )

        if order_total > total_voucher_balance:
            participant = getattr(account_balance, "participant", None)
            raise ValidationError(
                f"[{participant}] Order total ${order_total:.2f} "
                f"exceeds available voucher balance ${total_voucher_balance:.2f}."
            )

        logger.debug("[Voucher Validator] Voucher validation passed.")

    def validate_vouchers(self, items=None):
        """
        Validate order total against available voucher balance.
        
        Ensures:
        1. The AccountBalance has active vouchers.
        2. The order total does not exceed available voucher balance.
        """
        account_balance = self.account
        active_vouchers = self._get_active_vouchers(account_balance)
        
        # Validate voucher presence
        self._validate_voucher_presence(account_balance, active_vouchers)
        
        # Validate voucher balance
        items_to_validate = items if items is not None else self.items.all()
        order_total = Order.total_price(items_to_validate)
        total_voucher_balance = self._calculate_total_voucher_balance(active_vouchers)
        
        self._validate_voucher_balance(account_balance, order_total, total_voucher_balance)
        
        logger.info(
            "[Voucher Validator] Voucher #%s passed voucher validation.",
            self.pk
        )

    class Meta:
        ordering = ['id']

    def __str__(self) -> str:
        return f"Voucher ({self.pk})"

    def clean(self):
        """Validate voucher state and active field consistency."""
        # Prevent consumed vouchers from being active
        if self.state == "consumed" and self.active:
            raise ValidationError(
                "A consumed voucher cannot be set as active."
            )
        
        # Prevent active vouchers from being consumed
        if self.active and self.state == "consumed":
            raise ValidationError(
                "An active voucher cannot be set as consumed."
            )
        
        # Prevent changing state of a consumed voucher
        if self.pk:  # Only check for existing records
            try:
                old_instance = Voucher.objects.get(pk=self.pk)
                if (old_instance.state == "consumed" and
                        self.state != "consumed"):
                    raise ValidationError(
                        "Cannot change the state of a consumed voucher."
                    )
            except Voucher.DoesNotExist:
                pass

    @property
    def voucher_amnt(self) -> Decimal:
        """
        Compute the redeemable amount for this voucher.
        """
        return calculate_voucher_amount(self)


class OrderVoucher(models.Model):
    """Join model representing the application of a voucher to an order."""
    
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="applied_vouchers"
    )
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="order_applications"
    )
    applied_amount = models.DecimalField(max_digits=10, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        order_id = getattr(self.order, "id", None)
        voucher_id = getattr(self.voucher, "id", None)
        return (
            f"Order #{order_id} - Voucher {voucher_id} "
            f"(${self.applied_amount})"
        )
