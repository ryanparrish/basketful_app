# food_orders/admin.py
"""Admin configuration for Pantry app."""
# Django imports
from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponseRedirect
# First-party imports
from apps.orders.tasks.weekly_orders import create_weekly_combined_orders
# Local application imports
from .models import (
    Product, Category,
    Subcategory, OrderPacker,
    ProductLimit
)


class SubcategoryInline(admin.StackedInline):
    """Inline admin for Subcategory within Category."""
    model = Subcategory  # Ensure this references the actual model class
    extra = 1

   
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for Category with Subcategory inline."""
    list_display = ('name',)
    inlines = [SubcategoryInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model with image preview."""
    readonly_fields = ['image_preview']
    search_fields = ['name', 'description', 'category__name']

    def image_preview(self, obj):
        """Display a preview of the product image."""
        if obj.image:
            # Use format_html to safely construct the HTML and avoid mark_safe with unescaped input
            return format_html('<img src="{}" style="max-height: 200px;" />', obj.image.url)
        return "(No image uploaded)"

    image_preview.short_description = "Current Image"

    class Media:
        """Media class to include custom JS for image preview."""
        js = ('food_orders/js/admin_image_preview.js',)

 

admin.site.register(OrderPacker)
admin.site.register(ProductLimit)

