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


class VoucherRedemptionReportForm(forms.Form):
    """Form for filtering voucher redemption report."""
    
    DATE_RANGE_CHOICES = [
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_year', 'This Year'),
        ('custom', 'Custom Range'),
    ]
    
    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='this_month',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control date-range-select',
            'id': 'date-range-select'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control date-input',
            'type': 'date',
            'id': 'start-date'
        }),
        help_text="Required for custom date range"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control date-input',
            'type': 'date',
            'id': 'end-date'
        }),
        help_text="Required for custom date range"
    )
    
    program = forms.ModelChoiceField(
        queryset=Program.objects.all(),
        required=False,
        empty_label="All Programs",
        widget=forms.Select(attrs={
            'class': 'form-control program-select'
        })
    )
    
    voucher_type = forms.ChoiceField(
        choices=[
            ('', 'All Types'),
            ('grocery', 'Grocery'),
            ('life', 'Life'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control voucher-type-select'
        })
    )
    
    group_by = forms.ChoiceField(
        choices=[
            ('program', 'By Program'),
            ('participant', 'By Participant'),
        ],
        initial='program',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control group-by-select'
        }),
        label='Group Results'
    )
    
    def clean(self):
        """Validate custom date range fields."""
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range == 'custom':
            if not start_date:
                self.add_error('start_date', 'Start date is required for custom range.')
            if not end_date:
                self.add_error('end_date', 'End date is required for custom range.')
            if start_date and end_date and start_date > end_date:
                self.add_error('end_date', 'End date must be after start date.')
        
        return cleaned_data
