# orders/models.py
"""Models for food orders and related entities."""
# Standard library imports
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import logging
# Django imports
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint, F
from django.db.models.functions import ExtractWeek, ExtractYear

logger = logging.getLogger(__name__)


@dataclass
class OrderItemData:
    """Data structure for order item input."""
    product: models.Model
    quantity: int
    delete: bool = False


class OrderValidationLog(models.Model):
    """Stores validation errors for orders."""
    order = models.ForeignKey(
        "Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="validation_logs"
    )
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


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
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self) -> Decimal:
        """Calculate the total price of the order."""
        return sum(item.total_price() for item in self.items.all())

    def confirm(self):
        """Confirm the order after validation."""
        self.full_clean()
        self.status = "confirmed"
        self.save()

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

        # --- Hygiene balance ---
        hygiene_items = [
            item for item in self.items.select_related("product")
            if getattr(item.product.category, "name", "").lower() == "hygiene"
        ]
        hygiene_total = sum(item.total_price() for item in hygiene_items)
        hygiene_balance = getattr(self.account, "hygiene_balance", 0)
        if hygiene_total > hygiene_balance:
            errors.append(f"Hygiene limit exceeded: {hygiene_total} > {hygiene_balance}")

        # --- Category limits ---
        try:
            self._validate_category_limits()
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
            for msg in errors:
                OrderValidationLog.objects.create(order=self, error_message=str(msg))
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.full_clean()
            super().save(*args, **kwargs)

    # -----------------------------
    # Private helpers
    # -----------------------------
    def _aggregate_category_data(self):
        category_totals, category_units, category_products, category_objects = {}, {}, {}, {}
        for item in self.items.all():
            product = item.product
            subcategory = getattr(product, "subcategory", None)
            category = getattr(product, "category", None)
            obj = subcategory or category
            if not obj:
                continue
            cid = obj.id
            category_totals[cid] = category_totals.get(cid, 0) + item.quantity
            category_units[cid] = getattr(obj, "unit", "unit")
            category_products.setdefault(cid, []).append(product)
            category_objects[cid] = obj
        return category_totals, category_units, category_products, category_objects

    def _compute_allowed_quantity(self, product_manager, participant):
        allowed = product_manager.limit
        scope = product_manager.limit_scope
        if scope == "per_adult":
            allowed *= participant.adults
        elif scope == "per_child":
            allowed *= participant.children
        elif scope == "per_infant":
            allowed *= participant.diaper_count or 0
        elif scope == "per_household":
            allowed *= participant.household_size()
        return allowed

    def _validate_category_limits(self):
        category_totals, _, category_products, category_objects = self._aggregate_category_data()
        participant = getattr(self.account, "participant", None)
        for cid, total in category_totals.items():
            category = category_objects[cid]
            pm = getattr(category, "product_manager", None)
            if not pm or not pm.limit:
                continue
            allowed = self._compute_allowed_quantity(pm, participant)
            if total > allowed:
                product_names = ", ".join(p.name for p in category_products[cid])
                raise ValidationError(
                    f"Category limit exceeded for {category.name} "
                    f"({total} > {allowed}). Products: {product_names}"
                )


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
  
    program = models.ForeignKey("lifeskills.Program", on_delete=models.CASCADE, related_name="combined_orders")
    orders = models.ManyToManyField("Order", related_name="combined_orders", blank=True)
    # packed_by = models.ForeignKey("pantry.OrderPacker", on_delete=models.SET_NULL, null=True, blank=True, related_name="combined_orders")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    summarized_data = models.JSONField(default=dict, blank=True)
    is_parent = models.BooleanField(default=False)

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
            UniqueConstraint(
                F("program"),
                ExtractYear("created_at"),
                ExtractWeek("created_at"),
                name="unique_program_per_week",
            )
        ]

    def __str__(self):
        return f"{self.program.name} Combined Order ({self.created_at and self.created_at.strftime('%Y-%m-%d')})"
