# widgets.py
from django.forms.widgets import Select
from django.utils.html import format_html

class ProductSelectWithPrice(Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            try:
                from food_orders.models import Product
                product = Product.objects.get(pk=value)
                option['attrs']['data-price'] = str(product.price)
            except Product.DoesNotExist:
                pass
        return option
