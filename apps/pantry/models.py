# Standard library
"""Models for Food Orders application."""
import logging
# Django imports
from django.core.validators import MinValueValidator
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
        app_label = 'pantry'


class Subcategory(models.Model):
    """Model representing a subcategory of products."""
    name = models.CharField(max_length=100)
    category = models.ForeignKey(
        Category, 
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
        Category, on_delete=models.CASCADE, related_name="products"
    )
    subcategory = models.ForeignKey(
        Subcategory, on_delete=models.CASCADE, null=True, blank=True
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
        Category,
        on_delete=models.CASCADE,
        related_name="category_limits",
        null=True,
        blank=True,
    )

    subcategory = models.ForeignKey(
        Subcategory,
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


class OrderPacker(models.Model):
    
    name = models.CharField(max_length=100)
    programs = models.ManyToManyField(
        'lifeskills.Program', related_name='packers', blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.name)
