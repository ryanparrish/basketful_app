# apps/voucher/forms.py
"""Forms for voucher bulk creation."""
from django import forms
from apps.lifeskills.models import Program


class BulkVoucherConfigurationForm(forms.Form):
    """Form for configuring bulk voucher creation."""
    
    program = forms.ModelChoiceField(
        queryset=Program.objects.all(),
        required=True,
        help_text="Select the program to create vouchers for",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    voucher_type = forms.ChoiceField(
        choices=[
            ('grocery', 'Grocery'),
            ('life', 'Life'),
        ],
        required=True,
        initial='grocery',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    vouchers_per_participant = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=1,
        required=True,
        help_text="Number of vouchers to create per participant (1-10)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional notes or memo for these vouchers'
        }),
        help_text="Optional notes that will be added to all created vouchers"
    )


class BulkVoucherConfirmationForm(forms.Form):
    """Form for confirming bulk voucher creation."""
    
    confirmation = forms.BooleanField(
        required=True,
        label="I understand this action will create vouchers and cannot be undone",
        error_messages={
            'required': 'You must check the confirmation box to proceed.'
        },
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Hidden fields to carry over configuration
    program_id = forms.IntegerField(widget=forms.HiddenInput())
    voucher_type = forms.CharField(max_length=20, widget=forms.HiddenInput())
    vouchers_per_participant = forms.IntegerField(widget=forms.HiddenInput())
    notes = forms.CharField(required=False, widget=forms.HiddenInput())
