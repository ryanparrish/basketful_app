# orders/models.py
"""Models for food orders and related entities."""
# Standard library imports
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import logging
import secrets
from datetime import datetime
# Django imports
from django.db import models, transaction
from django.core.exceptions import ValidationError
# Local imports
from apps.pantry.models import CategoryLimitValidator
from apps.log.models import OrderValidationLog

logger = logging.getLogger(__name__)


@dataclass
class OrderItemData:
    """Data structure for order item input."""
    product: models.Model
    quantity: int
    delete: bool = False


class FailedOrderAttempt(models.Model):
    """Audit log for failed order attempts with debugging context."""
    # Identity
    participant = models.ForeignKey("account.Participant", on_delete=models.CASCADE, related_name="failed_attempts")
    user = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    idempotency_key = models.CharField(max_length=64, unique=True, db_index=True)
    
    # Cart snapshot
    cart_snapshot = models.JSONField(help_text="[{product_id, product_name, quantity, price}]")
    cart_hash = models.CharField(max_length=64, db_index=True)
    
    # Financial totals
    total_attempted = models.DecimalField(max_digits=8, decimal_places=2)
    food_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    hygiene_total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Balance context at time of attempt
    full_balance = models.DecimalField(max_digits=8, decimal_places=2)
    available_balance = models.DecimalField(max_digits=8, decimal_places=2)
    hygiene_balance = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Program pause context
    program_pause_active = models.BooleanField(default=False)
    program_pause_name = models.CharField(max_length=255, blank=True)
    voucher_multiplier = models.IntegerField(default=1)
    active_voucher_count = models.IntegerField(default=0)
    
    # Validation errors
    validation_errors = models.JSONField(help_text="[{type, message, amount_over}]")
    error_summary = models.TextField()
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['participant', '-created_at']),
            models.Index(fields=['cart_hash', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.participant} - ${self.total_attempted} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class Order(models.Model):
    """A food order."""
    user = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    account = models.ForeignKey(
        "account.AccountBalance",
        on_delete=models.PROTECT,
        related_name="orders"
    )
    order_date = models.DateTimeField(auto_now_add=True)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    success_viewed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("confirmed", "Confirmed"),
            ("packing", "Packing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
    )
    paid = models.BooleanField(default=False)
    go_fresh_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total amount spent on Go Fresh items in this order"
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_combined(self) -> bool:
        """Check if order has been included in a combined order."""
        return self.combined_orders.exists()

    def total_price(self) -> Decimal:
        """Calculate the total price of the order."""
        return sum(item.total_price() for item in self.items.all())

    def confirm(self):
        """
        Confirm the order after validation.
        NOTE: Validation should happen BEFORE this method is called.
        This method only updates status to confirmed.
        """
        self.status = "confirmed"
        self.save(update_fields=['status'])

    @staticmethod
    def _generate_order_number():
        """Generate a unique order number with format: ORD-YYYYMMDD-XXXXXX."""
        timestamp = datetime.now().strftime('%Y%m%d')
        # Generate 6 random alphanumeric characters for uniqueness
        random_part = secrets.token_hex(3).upper()  # 6 chars
        return f'ORD-{timestamp}-{random_part}'

    def _ensure_order_number(self):
        """Ensure order has a unique order number, generating one if needed."""
        if not self.order_number:
            max_attempts = 10
            for _ in range(max_attempts):
                candidate = self._generate_order_number()
                if not Order.objects.filter(order_number=candidate).exists():
                    self.order_number = candidate
                    return
            # If we couldn't generate unique number after max_attempts,
            # fall back to timestamp + pk (will be set after save)
            raise ValidationError(
                "Failed to generate unique order number after multiple attempts"
            )

    def clean(self):
        """
        Validate order constraints:
        - Hygiene balance
        - Category limits
        - Voucher totals
        """
        super().clean()
        if self.status != "confirmed":
            return

        errors = []

        # Check if order has been saved (has items)
        if not self.pk:
            # Order hasn't been saved yet, skip validation that requires items
            return

        # --- Available balance (food items) ---
        food_items = [
            item for item in self.items.select_related("product")
            if getattr(item.product.category, "name", "").lower() != "hygiene"
        ]
        food_total = sum(item.total_price() for item in food_items)
        available_balance = getattr(self.account, "available_balance", 0)
        if food_total > available_balance:
            errors.append(
                f"Food balance exceeded: ${food_total} > ${available_balance}"
            )

        # --- Hygiene balance ---
        hygiene_items = [
            item for item in self.items.select_related("product")
            if getattr(item.product.category, "name", "").lower() == "hygiene"
        ]
        hygiene_total = sum(item.total_price() for item in hygiene_items)
        hygiene_balance = getattr(self.account, "hygiene_balance", 0)
        if hygiene_total > hygiene_balance:
            errors.append(
                f"Hygiene balance exceeded: "
                f"${hygiene_total} > ${hygiene_balance}"
            )

        # --- Go Fresh balance ---
        go_fresh_items = [
            item for item in self.items.select_related("product")
            if item.product.category and item.product.category.name.lower() == "go fresh"
        ]
        go_fresh_total = sum(item.total_price() for item in go_fresh_items)
        go_fresh_balance = getattr(self.account, "go_fresh_balance", 0)
        # Only validate Go Fresh if the feature is enabled (go_fresh_balance > 0)
        if go_fresh_balance > 0 and go_fresh_total > go_fresh_balance:
            errors.append(
                f"Go Fresh balance exceeded: "
                f"${go_fresh_total:.2f} > ${go_fresh_balance:.2f}"
            )
        # Store go_fresh_total for tracking (will be saved when order is confirmed)
        self.go_fresh_total = go_fresh_total

        # --- Category limits ---
        try:
            participant = getattr(self.account, "participant", None)
            CategoryLimitValidator.validate_category_limits(
                self.items.all(), participant
            )
        except ValidationError as e:
            errors.extend(e.error_list if hasattr(e, "error_list") else [e])

        # --- Voucher validation ---
        for order_voucher in self.applied_vouchers.select_related("voucher").all():
            voucher = order_voucher.voucher
            try:
                voucher.validate_vouchers(self.items.all(), self.account)
            except ValidationError as e:
                errors.append(f"Voucher {voucher.code}: {e}")

        # --- Log errors and raise ---
        if errors:
            from django.db import transaction
            # Save logs in a separate transaction so they persist even if
            # the main transaction is rolled back
            for msg in errors:
                try:
                    with transaction.atomic():
                        OrderValidationLog.objects.create(
                            order=self,
                            message=str(msg)
                        )
                except Exception as log_error:
                    # Don't let logging failures prevent validation errors
                    logger.error(
                        f"Failed to create OrderValidationLog: {log_error}"
                    )
            raise ValidationError(errors)

    def _consume_vouchers(self):
        """
        Consume vouchers when order is confirmed.
        
        Rules:
        - If order total <= 1 voucher amount: consume 1 voucher
        - If order total > 1 voucher amount: consume both vouchers
        - Participants can have max 2 active vouchers
        """
        if self.status != "confirmed":
            return
        
        from apps.voucher.models import Voucher
        
        order_total = self.total_price()
        if order_total == 0:
            return
        
        # Get active grocery vouchers for this account (max 2)
        active_vouchers = list(Voucher.objects.filter(
            account=self.account,
            voucher_type='grocery',
            active=True,
            state='applied'
        ).order_by('created_at')[:2])  # Limit to 2 vouchers max
        
        if not active_vouchers:
            return
        
        # Calculate single voucher amount (they should all be the same)
        single_voucher_amount = active_vouchers[0].voucher_amnt if active_vouchers else Decimal('0')
        
        # Calculate total available voucher balance
        total_voucher_balance = sum(v.voucher_amnt for v in active_vouchers)
        
        # Validate order doesn't exceed voucher balance
        if order_total > total_voucher_balance:
            participant = getattr(self.account, 'participant', None)
            logger.error(
                f"Order {self.id}: Order total ${order_total} exceeds available "
                f"voucher balance ${total_voucher_balance}"
            )
            raise ValidationError(
                f"Order total ${order_total:.2f} exceeds available voucher balance "
                f"${total_voucher_balance:.2f} for {participant}"
            )
        
        # Determine how many vouchers to consume
        if order_total <= single_voucher_amount:
            # Order total is less than or equal to one voucher: consume 1
            vouchers_to_consume = active_vouchers[:1]
        else:
            # Order total is greater than one voucher: consume all available (max 2)
            vouchers_to_consume = active_vouchers
        
        # Mark vouchers as consumed and create OrderVoucher records
        from apps.voucher.models import OrderVoucher
        
        remaining = order_total
        for voucher in vouchers_to_consume:
            # Mark voucher as consumed - use update() to bypass editable=False
            applied_amount = min(voucher.voucher_amnt, remaining)
            remaining -= applied_amount
            
            notes_update = (voucher.notes or "") + f"Used on order {self.id} for ${applied_amount:.2f}; "
            
            # Use queryset update to bypass model field restrictions
            Voucher.objects.filter(pk=voucher.pk).update(
                active=False,
                state='consumed',
                notes=notes_update
            )
            
            # Create OrderVoucher record to track application
            OrderVoucher.objects.create(
                order=self,
                voucher=voucher,
                applied_amount=applied_amount
            )
        
        # Log the consumption
        if vouchers_to_consume:
            logger.info(
                f"Order {self.id}: Consumed {len(vouchers_to_consume)} voucher(s) "
                f"for total ${order_total} (single voucher amount: ${single_voucher_amount})"
            )

    def save(self, *args, **kwargs):
        # Generate order number if this is a new order
        if self.pk is None:
            self._ensure_order_number()
        
        # Track if status is changing to confirmed
        is_new = self.pk is None
        old_status = None
        
        if not is_new:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Order.DoesNotExist:
                pass
        
        with transaction.atomic():
            # Skip validation if only updating specific fields
            if 'update_fields' not in kwargs:
                self.full_clean()
            super().save(*args, **kwargs)
            
            # Consume vouchers if order is being confirmed
            if self.status == "confirmed" and old_status != "confirmed":
                self._consume_vouchers()


class OrderItem(models.Model):
    """An item within an order."""
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("pantry.Product", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    price_at_order = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        """Calculate total price for this order item."""
        return self.quantity * self.price

    def clean(self):
        if self.pk:
            old_order_id = OrderItem.objects.get(pk=self.pk).order_id
            if old_order_id != self.order_id:
                raise ValidationError(
                    f"Cannot move OrderItem {self.pk} from Order {old_order_id} to {self.order_id}"
                )
        if self.created_at and self.order and self.created_at < self.order.created_at:
            raise ValidationError(f"OrderItem {self.pk or '[new]'} cannot be created before parent order")

    def save(self, *args, **kwargs):
        # Ensure price_at_order is set
        if self.product_id:
            from django.apps import apps
            Product = apps.get_model("pantry", "Product")
            product = self.product or Product.objects.only("price").filter(pk=self.product_id).first()
            if product:
                if self.price_at_order is None:
                    self.price_at_order = product.price
                self.price = product.price
        super().save(*args, **kwargs)
        self.full_clean()


class CombinedOrder(models.Model):
    """
    Combined order for warehouse ordering and packing.
    
    For single-packer programs, this serves as both the warehouse order
    and the packing list. For multi-packer programs, PackingList records
    are created to split the work among packers.
    """
    
    # Split strategy choices (mirrors Program.SPLIT_STRATEGY_CHOICES)
    SPLIT_STRATEGY_CHOICES = [
        ('none', 'None (Single Packer)'),
        ('fifty_fifty', '50/50 Split'),
        ('round_robin', 'Round Robin'),
        ('by_category', 'By Category'),
    ]
    
    name = models.CharField(max_length=255, blank=True)
    program = models.ForeignKey(
        "lifeskills.Program",
        on_delete=models.CASCADE,
        related_name="combined_orders"
    )
    orders = models.ManyToManyField(
        "Order",
        related_name="combined_orders",
        blank=True
    )
    split_strategy = models.CharField(
        max_length=20,
        choices=SPLIT_STRATEGY_CHOICES,
        default='none',
        help_text="Strategy used to split this combined order among packers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    summarized_data = models.JSONField(default=dict, blank=True)
    is_parent = models.BooleanField(default=False)
    week = models.IntegerField(editable=False, null=True, blank=True)
    year = models.IntegerField(editable=False, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        """Auto-populate week and year from created_at on creation only."""
        # Only set week/year on initial creation to avoid unique constraint violations on update
        if self.pk is None:
            # Use timezone.now() since created_at isn't set yet (auto_now_add happens in DB)
            from django.utils import timezone
            now = self.created_at or timezone.now()
            self.week = now.isocalendar()[1]
            self.year = now.year
        super().save(*args, **kwargs)

    def summarized_items_by_category(self):
        
        summary = defaultdict(lambda: defaultdict(int))
        orders_qs = self.orders.all().prefetch_related(
            "account__participant__program", "items__product__category"
        )
        for order in orders_qs:
            participant = getattr(order.account, "participant", None)
            if not participant or participant.program != self.program:
                continue
            for item in order.items.all():
                product = item.product
                category_name = product.category.name if product.category else "Uncategorized"
                summary[category_name][product.name] += item.quantity
        return summary

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['program', 'week', 'year'],
                name='unique_program_per_week'
            )
        ]

    def __str__(self):
        if self.name:
            return f"{self.program.name} - {self.name}"
        return f"{self.program.name} Combined Order ({self.created_at and self.created_at.strftime('%Y-%m-%d')})"


class PackingSplitRule(models.Model):
    """
    Predefined rules for splitting orders by category among packers.
    
    Used when a program's split_strategy is 'by_category'. Each rule
    assigns specific categories/subcategories to a packer.
    """
    program = models.ForeignKey(
        "lifeskills.Program",
        on_delete=models.CASCADE,
        related_name="packing_split_rules"
    )
    packer = models.ForeignKey(
        "pantry.OrderPacker",
        on_delete=models.CASCADE,
        related_name="split_rules"
    )
    categories = models.ManyToManyField(
        "pantry.Category",
        related_name="split_rules",
        blank=True,
        help_text="Categories this packer is responsible for"
    )
    subcategories = models.ManyToManyField(
        "pantry.Subcategory",
        related_name="split_rules",
        blank=True,
        help_text="Subcategories this packer is responsible for (overrides category)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders_packing_split_rule'
        unique_together = [['program', 'packer']]
        verbose_name = "Packing Split Rule"
        verbose_name_plural = "Packing Split Rules"

    def __str__(self):
        category_names = ", ".join(c.name for c in self.categories.all()[:3])
        if self.categories.count() > 3:
            category_names += "..."
        return f"{self.program.name} - {self.packer.name}: {category_names or 'No categories'}"


class PackingList(models.Model):
    """
    A packing list for a specific packer from a combined order.
    
    Only created when a combined order has multiple packers.
    For single-packer programs, the CombinedOrder itself serves as the packing list.
    """
    combined_order = models.ForeignKey(
        "CombinedOrder",
        on_delete=models.CASCADE,
        related_name="packing_lists"
    )
    packer = models.ForeignKey(
        "pantry.OrderPacker",
        on_delete=models.CASCADE,
        related_name="packing_lists"
    )
    orders = models.ManyToManyField(
        "Order",
        related_name="packing_lists",
        blank=True,
        help_text="Orders assigned to this packer"
    )
    categories = models.ManyToManyField(
        "pantry.Category",
        related_name="packing_lists",
        blank=True,
        help_text="Categories this packer is responsible for (for by_category strategy)"
    )
    summarized_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Aggregated product quantities for this packer's portion"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders_packing_list'
        verbose_name = "Packing List"
        verbose_name_plural = "Packing Lists"

    def __str__(self):
        return f"{self.combined_order} - {self.packer.name}"

    def calculate_summarized_data(self):
        """
        Calculate aggregated product quantities for this packer's orders/categories.
        
        Returns dict of {category_name: {product_name: quantity}}
        """
        summary = defaultdict(lambda: defaultdict(int))
        
        # Get the split strategy from the combined order
        strategy = self.combined_order.split_strategy
        
        if strategy == 'by_category':
            # For by_category, filter items by assigned categories
            assigned_category_ids = set(self.categories.values_list('id', flat=True))
            
            for order in self.combined_order.orders.all():
                for item in order.items.select_related('product__category'):
                    product = item.product
                    if product.category_id in assigned_category_ids:
                        category_name = product.category.name if product.category else "Uncategorized"
                        summary[category_name][product.name] += item.quantity
        else:
            # For other strategies (fifty_fifty, round_robin), use assigned orders
            for order in self.orders.all():
                for item in order.items.select_related('product__category'):
                    product = item.product
                    category_name = product.category.name if product.category else "Uncategorized"
                    summary[category_name][product.name] += item.quantity
        
        return dict(summary)
