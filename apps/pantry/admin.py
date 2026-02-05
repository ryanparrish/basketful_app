hi# food_orders/admin.py
"""Admin configuration for Pantry app."""
# Django imports
from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied
# First-party imports
from apps.orders.tasks.weekly_orders import create_weekly_combined_orders
# Local application imports
from apps.pantry.models import (
    Product, Category,
    Subcategory, OrderPacker,
    ProductLimit, Tag
)

# Protected categories that cannot be modified or deleted
PROTECTED_CATEGORIES = ['hygiene', 'go fresh']


class SubcategoryInline(admin.StackedInline):
    """Inline admin for Subcategory within Category."""
    model = Subcategory  # Ensure this references the actual model class
    extra = 1

   
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for Category with Subcategory inline and protection for critical categories."""
    list_display = ('name_with_lock',)
    inlines = [SubcategoryInline]
    
    def name_with_lock(self, obj):
        """Display category name with lock icon if protected."""
        if obj and obj.name.lower() in PROTECTED_CATEGORIES:
            return format_html('<span>🔒 {}</span>', obj.name)
        return obj.name if obj else ''
    
    name_with_lock.short_description = 'Name'
    name_with_lock.admin_order_field = 'name'
    
    def get_readonly_fields(self, request, obj=None):
        """Make name field readonly for protected categories."""
        if obj and obj.name.lower() in PROTECTED_CATEGORIES:
            return ['name']
        return []
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of protected categories."""
        if obj and obj.name.lower() in PROTECTED_CATEGORIES:
            return False
        return super().has_delete_permission(request, obj)
    
    def delete_model(self, request, obj):
        """Prevent deletion of protected categories with clear error message."""
        if obj.name.lower() in PROTECTED_CATEGORIES:
            raise PermissionDenied(
                f"Cannot delete protected category: {obj.name}. "
                f"This category is required for the system."
            )
        super().delete_model(request, obj)
    
    def get_inlines(self, request, obj):
        """Only show subcategory inline for existing categories."""
        if obj:  # obj exists means we're editing an existing category
            return self.inlines
        return []  # Hide inlines when creating a new category


@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    """Admin for Subcategory with category filtering."""
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'category__name')
    ordering = ('category', 'name')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model with image preview."""
    readonly_fields = ['image_preview']
    search_fields = ['name', 'description', 'category__name', 'tags__name']
    list_display = ('name', 'category', 'subcategory', 'price', 'active', 'display_tags')
    list_filter = ('category', 'subcategory', 'active', 'tags')
    filter_horizontal = ('tags',)
    ordering = ('category__name', 'subcategory__name', 'name')

    def display_tags(self, obj):
        """Display tags as comma-separated list."""
        return ", ".join([tag.name for tag in obj.tags.all()[:5]])
    
    display_tags.short_description = 'Tags'

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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin for Tag model with product count."""
    list_display = ('name', 'slug', 'product_count', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    
    def product_count(self, obj):
        """Display count of products with this tag."""
        return obj.products.count()
    
    product_count.short_description = 'Products'


admin.site.register(OrderPacker)


@admin.register(ProductLimit)
class ProductLimitAdmin(admin.ModelAdmin):
    """Admin for ProductLimit with enhanced UI and explanations."""
    list_display = (
        'name',
        'get_category_display',
        'get_subcategory_display',
        'limit',
        'limit_scope',
        'get_limit_explanation'
    )
    list_filter = ('limit_scope', 'category', 'subcategory')
    search_fields = ('name', 'category__name', 'subcategory__name', 'notes')
    ordering = ('category__name', 'subcategory__name', 'name')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'notes'),
            'description': 'Give this limit a descriptive name.'
        }),
        ('Apply To', {
            'fields': ('category', 'subcategory'),
            'description': (
                '<strong>Choose what this limit applies to:</strong><br>'
                '• Select only <strong>Category</strong> to limit ALL '
                'products in that category<br>'
                '• Select both <strong>Category AND Subcategory</strong> '
                'to limit only products in that specific subcategory'
            )
        }),
        ('Limit Configuration', {
            'fields': ('limit', 'limit_scope'),
            'description': (
                '<strong>Set the quantity limit and scope:</strong><br>'
                '• <strong>Limit</strong>: Base number allowed<br>'
                '• <strong>Scope</strong>: How the limit is multiplied:<br>'
                '&nbsp;&nbsp;- <em>Per Adult</em>: limit × number of adults '
                '(e.g., 2 limit × 3 adults = 6 allowed)<br>'
                '&nbsp;&nbsp;- <em>Per Child</em>: limit × number of '
                'children<br>'
                '&nbsp;&nbsp;- <em>Per Infant</em>: limit × number of '
                'infants (diaper_count)<br>'
                '&nbsp;&nbsp;- <em>Per Household</em>: limit × total '
                'household size<br>'
                '&nbsp;&nbsp;- <em>Per Order</em>: limit applies to entire '
                'order (not multiplied)'
            )
        }),
    )

    def get_category_display(self, obj):
        """Display category name or 'N/A'."""
        return obj.category.name if obj.category else '—'
    get_category_display.short_description = 'Category'
    get_category_display.admin_order_field = 'category__name'

    def get_subcategory_display(self, obj):
        """Display subcategory name or 'All'."""
        if obj.subcategory:
            return obj.subcategory.name
        return 'All' if obj.category else '—'
    get_subcategory_display.short_description = 'Subcategory'
    get_subcategory_display.admin_order_field = 'subcategory__name'

    def get_limit_explanation(self, obj):
        """Provide a human-readable explanation of the limit."""
        scope = obj.limit_scope or 'per_household'
        limit = obj.limit

        scope_explanations = {
            'per_adult': f'{limit} per adult in household',
            'per_child': f'{limit} per child in household',
            'per_infant': f'{limit} per infant in household',
            'per_household': f'{limit} per household member',
            'per_order': f'{limit} total per order',
        }

        explanation = scope_explanations.get(scope, f'{limit} items')

        # Add example
        examples = {
            'per_adult': (
                f'e.g., household with 2 adults = {limit * 2} allowed'
            ),
            'per_child': (
                f'e.g., household with 3 children = {limit * 3} allowed'
            ),
            'per_infant': (
                f'e.g., household with 1 infant = {limit * 1} allowed'
            ),
            'per_household': (
                f'e.g., household of 4 = {limit * 4} allowed'
            ),
            'per_order': f'always {limit} items maximum',
        }

        example = examples.get(scope, '')

        return format_html(
            '<strong>{}</strong><br><small style="color: #666;">{}</small>',
            explanation,
            example
        )
    get_limit_explanation.short_description = 'How Limit Works'

