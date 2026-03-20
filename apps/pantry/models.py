# Standard library
"""Models for Food Orders application."""
import logging
from collections import defaultdict
# Django imports
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.db import models
from django.core.cache import cache
# Local app imports

logger = logging.getLogger(__name__)


class Category(models.Model):
    """Model representing a product category."""
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(
        default=0,
        help_text="Pick sequence for packing lists. 0 = top (newly created). Reorder via drag-and-drop in admin."
    )

    def __str__(self) -> str:
        return str(self.name)
    
    class Meta:
        """Meta options for Category."""
        verbose_name_plural = "Categories"
        db_table = 'food_orders_category'
        ordering = ['sort_order', 'name']


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


class Tag(models.Model):
    """Model representing a product tag for search enhancement."""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        db_table = 'food_orders_tag'
        ordering = ['name']
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    
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
    tags = models.ManyToManyField(
        'pantry.Tag',
        related_name='products',
        blank=True,
        help_text='Tags for search enhancement (e.g., "beef", "chicken", "gluten-free")'
    )

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

    sort_order = models.IntegerField(
        default=0,
        help_text="Pick sequence within category for packing lists. 0 = top (newly created). Reorder via drag-and-drop in admin."
    )

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        db_table = 'food_orders_product'
        ordering = ['sort_order', 'name']


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
        ordering = ['name']


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
            
            # Use tuple (type, id) as key to avoid ID collisions
            # e.g., ('category', 2) vs ('subcategory', 2) are different
            cid = (
                ('subcategory', obj.id) if subcategory
                else ('category', obj.id)
            )
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
    def _get_active_pause_multiplier():
        """
        Get the active program pause multiplier with caching.

        Returns a non-1 multiplier in two cases:
        1. A pause is currently in progress (pause_start <= now <= pause_end)
        2. An upcoming pause is within the ordering window (10–14 days out),
           meaning participants are ordering NOW for the pause period.

        Returns:
            tuple: (multiplier, pause_name) where multiplier is 1, 2, or 3
                   and pause_name is the name of the active pause or None
        """
        # Check cache first
        cache_key = 'active_pause_multiplier'
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Import here to avoid circular imports
        from apps.lifeskills.models import ProgramPause
        from django.utils import timezone
        from datetime import timedelta

        current_time = timezone.now()

        # 1. Currently in-progress pause
        active_pause = ProgramPause.objects.filter(
            pause_start__lte=current_time,
            pause_end__gte=current_time,
            archived=False,
        ).first()

        if active_pause:
            multiplier = active_pause.multiplier
            result = (multiplier, getattr(active_pause, 'reason', None) or 'Active Pause')
            cache.set(cache_key, result, 300)
            return result

        # 2. Upcoming pause in ordering window (10–14 days out).
        # Use a 15-day lookahead as a cheap DB pre-filter, then let the
        # model's timezone-aware multiplier property confirm the window.
        upcoming = ProgramPause.objects.filter(
            pause_start__gt=current_time,
            pause_start__lte=current_time + timedelta(days=15),
            archived=False,
        ).first()

        if upcoming and upcoming.multiplier > 1:
            result = (upcoming.multiplier, getattr(upcoming, 'reason', None) or 'Upcoming Pause')
            cache.set(cache_key, result, 300)
            return result

        result = (1, None)
        # Cache for 5 minutes to reduce database queries
        cache.set(cache_key, result, 300)
        return result
    
    @staticmethod
    def compute_allowed_quantity(product_limit, participant, pause_multiplier=1):
        """
        Compute the allowed quantity based on limit scope and pause multiplier.
        
        Args:
            product_limit: ProductLimit instance
            participant: Participant instance
            pause_multiplier: Program pause multiplier (1, 2, or 3)
            
        Returns:
            int: Calculated allowed quantity (limit × pause_multiplier × scope_factor)
        """
        # Apply pause multiplier to base limit first
        base_limit = product_limit.limit * pause_multiplier
        allowed = base_limit
        scope = product_limit.limit_scope
        
        # Then apply scope factor
        if scope == "per_adult":
            allowed = base_limit * participant.adults
        elif scope == "per_child":
            allowed = base_limit * participant.children
        elif scope == "per_infant":
            allowed = base_limit * (participant.diaper_count or 0)
        elif scope == "per_household":
            allowed = base_limit * participant.household_size()
        # per_order scope doesn't multiply, just uses base_limit
        
        return allowed
    
    @staticmethod
    def validate_category_limits(order_items, participant):
        """
        Validate that order items don't exceed category limits.
        Applies program pause multiplier when active.
        
        Args:
            order_items: QuerySet or list of order items
            participant: Participant instance
            
        Raises:
            ValidationError: If any category limit is exceeded
        """
        # Get active pause multiplier once for all validations
        pause_multiplier, pause_name = CategoryLimitValidator._get_active_pause_multiplier()
        
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
                product_limit, participant, pause_multiplier
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
                
                # Build limit description with pause context
                if pause_multiplier > 1:
                    limit_description = (
                        f"{product_limit.limit} "
                        f"({product_limit.limit * pause_multiplier} with {pause_multiplier}x pause)"
                    )
                else:
                    limit_description = str(product_limit.limit)
                
                error_msg = (
                    f"Limit exceeded for {category_type} "
                    f"'{category.name}' (scope: {scope}, "
                    f"limit: {limit_description} {scope_description}): "
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
