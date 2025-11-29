# apps/account/forms.py
"""Forms for account app including custom login and participant forms."""
#Django imports
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django_recaptcha.fields import ReCaptchaField
from django.contrib.auth import get_user_model
from django import forms
# First-party imports
from apps.account.models import Participant


class CustomLoginForm(AuthenticationForm):
    """Custom login form with reCAPTCHA support."""
    def __init__(self, *args, **kwargs):
        use_captcha = kwargs.pop('use_captcha', False)
        super().__init__(*args, **kwargs)
        
        if use_captcha:
            self.fields['captcha'] = ReCaptchaField()
User = get_user_model()


class CustomUserCreationForm(forms.ModelForm):
    """Form for creating a new user without username/password fields."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')  # no username or password here



class ParticipantAdminForm(forms.ModelForm):
    """Admin form for Participant with option to create linked user."""
    create_user = forms.BooleanField(required=False, label="Create linked user?")

    class Meta:
        model = Participant
        fields = '__all__'


class ParticipantUpdateForm(forms.ModelForm):
    """Form for updating Participant email and name only."""
    class Meta:
        model = Participant
        fields = ['email', 'name', ]
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
        }
