"""
Custom FilterSet for the Orders app.

Extends the simple filterset_fields approach to support
multi-value filtering (e.g. ?account__participant__program=1&account__participant__program=3)
via ModelMultipleChoiceFilter.
"""
from django_filters import rest_framework as filters
from apps.orders.models import Order
from apps.lifeskills.models import Program


class OrderFilter(filters.FilterSet):
    """FilterSet for Order — supports all original fields plus multi-program."""

    # Original exact-match fields (mirrors the old filterset_fields list)
    status = filters.CharFilter(field_name='status', lookup_expr='exact')
    paid = filters.BooleanFilter(field_name='paid')
    account = filters.NumberFilter(field_name='account', lookup_expr='exact')
    user = filters.NumberFilter(field_name='user', lookup_expr='exact')

    # Multi-value program filter:
    # Accepts a single value (?account__participant__program=1)
    # OR repeated params  (?account__participant__program=1&account__participant__program=3)
    account__participant__program = filters.ModelMultipleChoiceFilter(
        field_name='account__participant__program',
        queryset=Program.objects.all(),
        conjoined=False,   # OR semantics: show orders belonging to ANY of the selected programs
    )

    class Meta:
        model = Order
        fields = [
            'status',
            'paid',
            'account',
            'user',
            'account__participant__program',
        ]
