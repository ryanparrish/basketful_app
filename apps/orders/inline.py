import json
from .models import OrderItem
from django.contrib import admin
from .forms import OrderItemInlineForm, OrderItemInlineFormSet


class OrderItemInline(admin.TabularInline):
    """Inline admin for OrderItems with custom form and formset."""
    model = OrderItem
    form = OrderItemInlineForm
    formset = OrderItemInlineFormSet
    extra = 1
    fields = ('product', 'quantity', 'price')
    readonly_fields = ('price',)

    class Media:
        """Media class to include custom JS."""
        js = ('food_orders/js/orderitem_inline.js',)

    def get_formset(self, request, obj=None, **kwargs):
        """
        Add a JSON map of product IDs -> prices to the formset for client-side JS.
        """
        from apps.pantry.models import Product

        formset = super().get_formset(request, obj, **kwargs)
        # If Product is not a Django model, replace with appropriate data source
        products = getattr(Product, 'objects', None)
        if products is not None:
            product_list = products.all().values('id', 'price')
            formset.product_json = json.dumps({str(p['id']): float(p['price']) for p in product_list})
        else:
            # Fallback: if Product is not a model, get product data another way
            product_list = getattr(Product, 'get_all_products', lambda: [])()
            formset.product_json = json.dumps({str(p['id']): float(p['price']) for p in product_list})
        return formset

    def save_new(self, form, commit=True):
        """
        Optional: use order_utils to handle any preprocessing before save.
        """
        instance = super().save_new(form, commit=False)
        # If you have logic in order_utils that sets prices or adjusts data:
        from .utils.order_utils import preprocess_order_item
        preprocess_order_item(instance)
        if commit:
            instance.save()
        return instance

    def clean(self):
        """
        Delegate validation to order_utils.
        """
        super().clean()
        account = getattr(self.instance, 'account', None)
        participant = getattr(account, 'participant', None)
        from .utils.order_utils import validate_order_items
        validate_order_items(self.forms, participant, account)
