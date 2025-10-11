from django.contrib import admin
from .models import OrderItem,Product
from .forms import OrderItemInlineForm, OrderItemInlineFormSet
import json 
from .models import VoucherLog

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemInlineForm
    formset = OrderItemInlineFormSet
    extra = 1
    fields = ('product', 'quantity', 'price')
    readonly_fields = ('price',)

    class Media:
        js = ('food_orders/js/orderitem_inline.js',)

    def get_formset(self, request, obj=None, **kwargs):
        """
        Add a JSON map of product IDs -> prices to the formset for client-side JS.
        """
        formset = super().get_formset(request, obj, **kwargs)
        products = Product.objects.all().values('id', 'price')
        formset.product_json = json.dumps({str(p['id']): float(p['price']) for p in products})
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


class VoucherLogInline(admin.TabularInline):
    model = VoucherLog
    fk_name = 'voucher'   # tells Django which FK to use
    fields = (
        'participant',
        'message',
        'log_type',
        'balance_before',
        'balance_after',
        'created_at',
    )
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
