# food_orders/forms.py
from django.core.exceptions import ValidationError
from django import forms
from django.forms import BaseInlineFormSet
from .models import OrderItem


# --------------------------
# Single OrderItem Form
# --------------------------
class OrderItemInlineForm(forms.ModelForm):
    """Form for individual OrderItem with validation."""
    class Meta:
        model = OrderItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity', 0)

        if not product:
            raise ValidationError("Product is required.")
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")

        return cleaned_data


# --------------------------
# Formset for multiple OrderItems
# --------------------------
class OrderItemInlineFormSet(BaseInlineFormSet):
    """Formset for multiple OrderItems with overall validation."""
    def clean(self):
        super().clean()

        # Skip if no parent instance
        if not self.instance:
            return

        items = []
        for form in self.forms:
            # Skip empty or deleted forms
            if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
                continue

            product = form.cleaned_data.get('product')
            quantity = form.cleaned_data.get('quantity', 0)

            # Already validated in the individual form, but double-check
            if not product or quantity <= 0:
                continue

            items.append({"product": product, "quantity": quantity})

        # Attach to the parent Order instance for model-level validation
        self.instance._pending_items = items

        # Trigger model-level validation (e.g
