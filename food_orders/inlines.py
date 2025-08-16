from django.contrib import admin
from .models import OrderItem

class OrderItemInline(admin.TabularInline):
    """Allows editing OrderItems directly in the Order admin page."""
    model = OrderItem
    extra = 0  # no extra blank rows
    autocomplete_fields = ['product']  # optional: for product search
