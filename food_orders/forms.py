from django import forms
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import OrderItem, Voucher, ProductManager
from decimal import Decimal
from django.contrib import admin
from .models import Participant
from django.contrib.auth.models import User
from .utils import generate_memorable_password, generate_unique_username
from django import forms
from django_recaptcha.fields import ReCaptchaField
from django.contrib.auth.forms import AuthenticationForm



class OrderItemInlineForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = '__all__'


class OrderItemInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.product_json = getattr(self, 'product_json', '{}')
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()

        participant = getattr(self.instance.account, 'participant', None)
        if not participant:
            print("[FormSet] No participant found — skipping validation.")
            return print(f"[FormSet] Validating for Participant: {participant}")
    
        scoped_totals = {}

        for form in self.forms:
            if form.cleaned_data.get('DELETE', False):
                continue

            product = form.cleaned_data.get("product")
            quantity = form.cleaned_data.get("quantity", 0)

            if not product or not product.category:
                print(f"[FormSet] Skipping product {product} (missing category)")
                continue

            productmanager = getattr(product.category, 'product_manager', None)
            if not productmanager:
                print(f"[FormSet] No ProductManager for category: {product.category}")
                continue

            scope = productmanager.limit_scope
            limit_quantity = productmanager.limit

            if not scope or not limit_quantity:
                print(f"[FormSet] Skipping validation for product {product.name} (missing scope/limit)")
                continue
        # Compute allowed limit by scope
            if scope == "per_adult":
                allowed = limit_quantity * participant.adults
            elif scope == "per_child":
                allowed = limit_quantity * participant.children
            elif scope == "per_infant":
                allowed = limit_quantity if participant.infant else 0
            elif scope == "per_household":
                allowed = limit_quantity * participant.household_size()
            elif scope == "per_order":
                allowed = limit_quantity
            else:
                print(f"[FormSet] Unknown scope: {scope}")
                continue

            # Determine if this is a weight-based product
            use_weight = product.weight_lbs and product.weight_lbs > 0
            unit = "lbs" if use_weight else "items"
            value = quantity * product.weight_lbs if use_weight else quantity
            key = f"{product.category.id}:{scope}:{unit}"
            scoped_totals.setdefault(key, 0)
            scoped_totals[key] += value

            print(f"[FormSet] Product: {product.name}, Category: {product.category.name}, "
              f"Scope: {scope}, Limit: {allowed} {unit}, Current Total: {scoped_totals[key]} {unit}")

            if scoped_totals[key] > allowed:
                raise ValidationError(
                f"Limit exceeded for {product.category.name} ({unit}, scope: {scope}): "
                f"{scoped_totals[key]} > allowed {allowed}"
            )

        print("[FormSet] Validation completed.\n")

        hygiene_total = 0
        order_total = 0

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE", False):
                continue

            product = form.cleaned_data["product"]
            quantity = form.cleaned_data["quantity"]
            line_total = product.price * quantity
            order_total += line_total

            if product.category.name.lower() == "hygiene":
                hygiene_total += line_total

        # Access account balances through the Order instance
            account_balance = self.instance.account
        # Business Rule 1: Hygiene total must not exceed hygiene balance
            if hygiene_total > account_balance.hygiene_balance:
                raise ValidationError(
                    f"Hygiene items total ${hygiene_total:.2f}, which exceeds hygiene balance of ${account_balance.hygiene_balance:.2f}."
                )

        # Business Rule 2: Total order must not exceed total voucher balance
            if order_total > account_balance.voucher_balance:
                raise ValidationError(
                    f"Order total ${order_total:.2f} exceeds available voucher balance of ${account_balance.voucher_balance:.2f}."
                )

class ParticipantAdminForm(forms.ModelForm):
    create_user = forms.BooleanField(required=False, label="Create linked user?")

    class Meta:
        model = Participant
        fields = '__all__'

    def save(self, commit=True):
        participant = super().save(commit=False)

        if self.cleaned_data.get('create_user') and not participant.user:
            username = generate_unique_username(participant.name)
            password = generate_memorable_password()
            user = User.objects.create_user(username=username, password=password, email=participant.email)
            participant.user = user
            print(f"[INFO] Created user '{username}' with password: {password}")

        if commit:
            participant.save()
        return participant
    
class ParticipantUpdateForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['email', 'name', ]
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }
# forms.py

class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        use_captcha = kwargs.pop('use_captcha', False)
        super().__init__(*args, **kwargs)
        
        if use_captcha:
            self.fields['captcha'] = ReCaptchaField()
