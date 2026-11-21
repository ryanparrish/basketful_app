# food_orders/forms.py
from django.core.exceptions import ValidationError
from django import forms
from django.forms import BaseInlineFormSet
from .models import OrderItem
from apps.lifeskills.models import Program


# --------------------------
# Combined Order Creation Form
# --------------------------
class CreateCombinedOrderForm(forms.Form):
    """
    Form for creating a combined order with custom time frame and program.
    Supports strategy override for advanced users.
    """
    program = forms.ModelChoiceField(
        queryset=None,
        required=True,
        label="Program",
        help_text="Select the program for which to combine orders"
    )
    start_date = forms.DateField(
        required=True,
        label="Start Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Start date of the time frame"
    )
    end_date = forms.DateField(
        required=True,
        label="End Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="End date of the time frame"
    )
    split_strategy_override = forms.ChoiceField(
        required=False,
        label="Split Strategy Override",
        choices=[
            ('', 'Use Program Default'),
            ('none', 'None (Single Packer)'),
            ('fifty_fifty', '50/50 Split'),
            ('round_robin', 'Round Robin'),
            ('by_category', 'By Category'),
        ],
        help_text="Override the program's default split strategy (optional)"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Import here to avoid circular imports
        from apps.lifeskills.models import Program
        self.fields['program'].queryset = Program.objects.all()
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("End date must be after start date.")
        
        return cleaned_data
    
    def get_effective_strategy(self):
        """
        Get the effective split strategy (override or program default).
        
        Returns:
            str: The split strategy to use
        """
        override = self.cleaned_data.get('split_strategy_override')
        if override:
            return override
        
        program = self.cleaned_data.get('program')
        if program:
            return program.default_split_strategy
        
        return 'none'


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


# --------------------------
# Inventory Report Form (Issue #143)
# --------------------------
class InventoryReportForm(forms.Form):
    """Form for filtering the inventory report by date range.

    Mirrors VoucherRedemptionReportForm (apps/voucher/forms.py), with an
    added 'last_6_months' preset (the pantry team's planning horizon) and a
    grouping choice: whole range, weekly buckets, or monthly buckets.
    """

    DATE_RANGE_CHOICES = [
        ('last_6_months', 'Last 6 Months'),
        ('this_week', 'This Week'),
        ('this_month', 'This Month'),
        ('last_month', 'Last Month'),
        ('this_year', 'This Year'),
        ('custom', 'Custom Range'),
    ]

    GROUPING_CHOICES = [
        ('range', 'Whole Range'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='last_6_months',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control date-range-select',
            'id': 'date-range-select',
        }),
    )

    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control date-input',
            'type': 'date',
            'id': 'start-date',
        }),
        help_text="Required for custom date range",
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control date-input',
            'type': 'date',
            'id': 'end-date',
        }),
        help_text="Required for custom date range",
    )

    program = forms.ModelChoiceField(
        queryset=Program.objects.all(),
        required=False,
        empty_label="All Programs",
        widget=forms.Select(attrs={
            'class': 'form-control program-select',
        }),
    )

    grouping = forms.ChoiceField(
        choices=GROUPING_CHOICES,
        initial='range',
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control group-by-select',
        }),
        label='Group Results',
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
