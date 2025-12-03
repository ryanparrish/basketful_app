# Standard library
"""Models for Food Orders application."""
import logging
from collections import defaultdict
# Django imports
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.db import models
# Local app imports

logger = logging.getLogger(__name__)


class Category(models.Model):
    """Model representing a product category."""
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return str(self.name)
    
    class Meta:
        """Meta options for Category."""
        verbose_name_plural = "Categories"
        db_table = 'food_orders_category'
        


class Subcategory(models.Model):
    """Model representing a subcategory of products."""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        'pantry.Category', 
        on_delete=models.CASCADE, 
        related_name='subcategories'
    )

    def __str__(self):
        return f"{self.category.name} > {self.name}"

    class Meta:
        db_table = 'food_orders_subcategory'
    
# Class to represent a product in inventory


class Product(models.Model):
    """Model representing a product in the inventory."""
    is_meat = models.BooleanField(default=False)
    weight_lbs = models.DecimalField(
        max_digits=4, decimal_places=2, default=0
    )  # e.g., 1.00 for beef, 2.00 for chicken
    category = models.ForeignKey(
        'pantry.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    subcategory = models.ForeignKey(
        'pantry.Subcategory', on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
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
        """
        Retrieve the applicable limit for the product
        based on its category and subcategory.
        """
        subcat_limit = (
            ProductLimit.objects
            .filter(subcategory=product.subcategory)
            .order_by('limit')
            .first()
        )
        cat_limit = (
            ProductLimit.objects
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

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        db_table = 'food_orders_product'
        
  

class ProductLimit(models.Model):
    """Model to manage product limits per category or subcategory."""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        'pantry.Category',
        on_delete=models.CASCADE,
        related_name="category_limits",
        null=True,
        blank=True,
    )

    subcategory = models.ForeignKey(
        'pantry.Subcategory',
        on_delete=models.CASCADE,
        related_name="subcategory_limits",
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True, null=True)
    limit = models.IntegerField(
        default=2,
        validators=[MinValueValidator(1)],
        help_text=(
            "Maximum number of products allowed in this category per order."
        )
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

    def __str__(self) -> str:
        return str(self.name)
    
    class Meta:
        db_table = 'food_orders_product_limit'

class OrderPacker(models.Model):
    
    name = models.CharField(max_length=100)
    programs = models.ManyToManyField(
        'lifeskills.Program', related_name='packers', blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.name)
    class Meta:
        db_table = 'food_orders_order_packer'


class CategoryLimitValidator:
    """Utility class for validating category limits on orders."""
    
    @staticmethod
    def aggregate_category_data(order_items):
        """
        Aggregate order items by category/subcategory.
        
        Returns:
            tuple: (category_totals, category_units, category_products, category_objects)
        """
        category_totals = defaultdict(int)
        category_units = {}
        category_products = defaultdict(list)
        category_objects = {}
        
        for item in order_items:
            product = item.product
            subcategory = getattr(product, "subcategory", None)
            category = getattr(product, "category", None)
            obj = subcategory or category
            
            if not obj:
                continue
                
            cid = obj.id
            category_totals[cid] += item.quantity
            category_units[cid] = getattr(obj, "unit", "unit")
            category_products[cid].append(product)
            category_objects[cid] = obj
            
        return (
            dict(category_totals),
            category_units,
            dict(category_products),
            category_objects
        )
    
    @staticmethod
    def compute_allowed_quantity(product_limit, participant):
        """
        Compute the allowed quantity based on limit scope.
        
        Args:
            product_limit: ProductLimit instance
            participant: Participant instance
            
        Returns:
            int: Calculated allowed quantity
        """
        allowed = product_limit.limit
        scope = product_limit.limit_scope
        
        if scope == "per_adult":
            allowed *= participant.adults
        elif scope == "per_child":
            allowed *= participant.children
        elif scope == "per_infant":
            allowed *= participant.diaper_count or 0
        elif scope == "per_household":
            allowed *= participant.household_size()
        
        return allowed
    
    @staticmethod
    def validate_category_limits(order_items, participant):
        """
        Validate that order items don't exceed category limits.
        
        Args:
            order_items: QuerySet or list of order items
            participant: Participant instance
            
        Raises:
            ValidationError: If any category limit is exceeded
        """
        category_totals, _, category_products, category_objects = \
            CategoryLimitValidator.aggregate_category_data(order_items)
        
        errors = []
        
        for cid, total in category_totals.items():
            category = category_objects[cid]
            
            # Get the product limit for this category
            product_limit = ProductLimit.objects.filter(
                category=(
                    category if isinstance(category, Category) 
                    else category.category
                ),
                subcategory=(
                    category if isinstance(category, Subcategory) 
                    else None
                )
            ).first()
            
            if not product_limit or not product_limit.limit:
                continue
            
            allowed = CategoryLimitValidator.compute_allowed_quantity(
                product_limit, participant
            )
            
            if total > allowed:
                # Build detailed error message
                category_type = (
                    "Subcategory" if isinstance(category, Subcategory) 
                    else "Category"
                )
                
                # Get individual product details
                product_details = []
                for p in category_products[cid]:
                    # Find the quantity for this specific product
                    product_qty = sum(
                        item.quantity for item in order_items
                        if item.product.id == p.id
                    )
                    product_details.append(
                        f"{p.name} (qty: {product_qty})"
                    )
                
                product_list = ", ".join(product_details)
                
                # Build scope description
                scope = product_limit.limit_scope or "per_household"
                scope_description = {
                    "per_adult": f"{participant.adults} adult(s)",
                    "per_child": f"{participant.children} child(ren)",
                    "per_infant": (
                        f"{participant.diaper_count or 0} infant(s)"
                    ),
                    "per_household": (
                        f"household of {participant.household_size()}"
                    ),
                    "per_order": "per order"
                }.get(scope, scope)
                
                error_msg = (
                    f"Limit exceeded for {category_type} "
                    f"'{category.name}' (scope: {scope}, "
                    f"limit: {product_limit.limit} {scope_description}): "
                    f"Ordered {total}, allowed {allowed}. "
                    f"Products: {product_list}"
                )
                
                logger.warning(
                    f"Category limit violation - "
                    f"Participant: {participant.name}, "
                    f"{category_type}: {category.name}, "
                    f"Ordered: {total}, Allowed: {allowed}, "
                    f"Scope: {scope}, Products: {product_list}"
                )
                
                errors.append(error_msg)
        
        if errors:
            raise ValidationError(errors)
