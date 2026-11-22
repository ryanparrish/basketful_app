"""Report endpoints for the React staff admin.

Inventory report (Issue #143): GET /api/v1/reports/inventory/
    ?date_range=last_6_months|this_week|this_month|last_month|this_year|custom
    &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD   (custom only)
    &program=<id>                                 (optional)
    &grouping=range|weekly|monthly
    &export=csv                                   (optional: download CSV)

The numbers and their rules live in apps/orders/inventory_report.py; the
JSON and the CSV are built from the same data, so they always match.
"""
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsStaffUser
from apps.lifeskills.models import Program
from apps.orders.inventory_report import (
    COUNTED_STATUSES,
    DATE_RANGE_CHOICES,
    GROUPING_CHOICES,
    MAX_RANGE_DAYS,
    _generate_csv_report,
    _get_date_range,
    _get_inventory_data,
)


class InventoryReportParamsSerializer(serializers.Serializer):
    """Validates the report's query parameters."""
    date_range = serializers.ChoiceField(
        choices=DATE_RANGE_CHOICES, default='last_6_months'
    )
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    program = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all(), required=False, allow_null=True
    )
    grouping = serializers.ChoiceField(choices=GROUPING_CHOICES, default='range')
    export = serializers.ChoiceField(choices=['csv'], required=False)

    def validate(self, attrs):
        if attrs['date_range'] == 'custom':
            start, end = attrs.get('start_date'), attrs.get('end_date')
            errors = {}
            if not start:
                errors['start_date'] = 'Start date is required for a custom range.'
            if not end:
                errors['end_date'] = 'End date is required for a custom range.'
            if start and end and start > end:
                errors['end_date'] = 'End date must be on or after the start date.'
            if start and end and (end - start).days > MAX_RANGE_DAYS:
                errors['end_date'] = 'Choose a range of three years or less.'
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


def _money(value):
    return f'{value:.2f}'


def _serialize(report_data, start_date, end_date, grouping, program):
    """JSON shape for the React page. Money is a 2-decimal string so the
    browser never shows float rounding; dates are ISO strings."""
    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'grouping': grouping,
        'program': program.pk if program else None,
        'program_name': program.name if program else None,
        'counted_statuses': list(COUNTED_STATUSES),
        'items': [
            {**row, 'total_cost': _money(row['total_cost'])}
            for row in report_data['items']
        ],
        'program_costs': [
            {**row, 'total_cost': _money(row['total_cost'])}
            for row in report_data['program_costs']
        ],
        'grand_total': _money(report_data['grand_total']),
        'participants_per_week': [
            {
                **row,
                'week_start': row['week_start'].isoformat(),
                'week_end': row['week_end'].isoformat(),
                'counted_from': row['counted_from'].isoformat(),
                'counted_to': row['counted_to'].isoformat(),
            }
            for row in report_data['participants_per_week']
        ],
    }


class InventoryReportView(APIView):
    """Inventory report by date range (staff only). JSON, or CSV with
    ?export=csv."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        params = InventoryReportParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        start_date, end_date = _get_date_range(
            data['date_range'], data.get('start_date'), data.get('end_date')
        )
        program = data.get('program')
        grouping = data['grouping']
        report_data = _get_inventory_data(
            start_date, end_date, program, grouping
        )

        if data.get('export') == 'csv':
            return _generate_csv_report(
                report_data, start_date, end_date, grouping
            )
        return Response(
            _serialize(report_data, start_date, end_date, grouping, program)
        )
