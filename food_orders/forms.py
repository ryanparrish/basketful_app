from django import forms
from .models import OrderItem, Participant
from django.contrib.auth.models import User
from django_recaptcha.fields import ReCaptchaField
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django import forms
from django.forms import BaseInlineFormSet
from django.core.exceptions import ValidationError

# --------------------------
# Single OrderItem Form
# --------------------------
class OrderItemInlineForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = '__all__'

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


class ParticipantAdminForm(forms.ModelForm):

    create_user = forms.BooleanField(required=False, label="Create linked user?")

    class Meta:
        model = Participant
        fields = '__all__'

class ParticipantUpdateForm(forms.ModelForm):
    class Meta:
        model = Participant\
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
User = get_user_model()

class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')  # no username or password here
