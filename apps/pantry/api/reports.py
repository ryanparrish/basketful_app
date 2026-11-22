"""Stock forecast endpoint for the React staff admin (Issue #148).

GET /api/v1/reports/stock-forecast/
    ?history_weeks=12&cover_weeks=4&safety_weeks=1   (defaults shown)
    &category=<id>&status=critical|low|ok|insufficient_history
    &product=<id>        (one product, e.g. the product page's usage panel)
    &export=csv          (reorder list: products with a suggested reorder)

The numbers come from apps.pantry.forecast.compute_forecast, which the
products list column and the forecast alert email also use.
"""
import csv

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsStaffUser
from apps.pantry.forecast import (
    DEFAULT_COVER_WEEKS,
    DEFAULT_HISTORY_WEEKS,
    DEFAULT_SAFETY_WEEKS,
    MIN_USABLE_WEEKS,
    STATUS_CHOICES,
    compute_forecast,
)
from apps.pantry.models import Category, Product


class StockForecastParamsSerializer(serializers.Serializer):
    history_weeks = serializers.IntegerField(
        min_value=MIN_USABLE_WEEKS, max_value=52, default=DEFAULT_HISTORY_WEEKS
    )
    cover_weeks = serializers.IntegerField(
        min_value=1, max_value=26, default=DEFAULT_COVER_WEEKS
    )
    safety_weeks = serializers.IntegerField(
        min_value=0, max_value=8, default=DEFAULT_SAFETY_WEEKS
    )
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True
    )
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES, required=False)
    export = serializers.ChoiceField(choices=['csv'], required=False)


def _iso(value):
    return value.isoformat() if value else None


def _serialize_row(row):
    return {
        **row,
        'runout_date': _iso(row['runout_date']),
        'last_received_at': _iso(row['last_received_at']),
        'history': [
            {**week, 'week_start': week['week_start'].isoformat()}
            for week in row['history']
        ],
    }


def _csv_safe(value):
    """Neutralise spreadsheet formula injection in a text cell."""
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


def _reorder_csv(rows, params):
    today = timezone.localdate()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="reorder_list_{today.isoformat()}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        f"Reorder list, {today.isoformat()}: covers {params['cover_weeks']} "
        f"week(s) + {params['safety_weeks']} safety week(s), usage from the "
        f"last {params['history_weeks']} weeks"
    ])
    writer.writerow([
        'Product', 'Category', 'On hand', 'Pending orders', 'Available',
        'Weekly usage', 'Weeks left', 'Runs out about', 'Suggested reorder',
    ])
    for row in rows:
        if not row['suggested_reorder']:
            continue
        writer.writerow([
            _csv_safe(row['product_name']),
            _csv_safe(row['category']),
            row['quantity_in_stock'],
            row['pending_units'],
            row['available'],
            row['weekly_usage'],
            '' if row['weeks_left'] is None else row['weeks_left'],
            _iso(row['runout_date']) or '',
            row['suggested_reorder'],
        ])
    return response


class StockForecastView(APIView):
    """Pantry-wide stock forecast (staff only). JSON, or CSV with ?export=csv."""
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        params = StockForecastParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        product = data.get('product')
        rows = compute_forecast(
            history_weeks=data['history_weeks'],
            cover_weeks=data['cover_weeks'],
            safety_weeks=data['safety_weeks'],
            category=data.get('category'),
            product_ids=[product.pk] if product else None,
        )
        if data.get('status'):
            rows = [row for row in rows if row['status'] == data['status']]
        if data.get('export') == 'csv':
            return _reorder_csv(rows, data)
        return Response({
            'generated_on': timezone.localdate().isoformat(),
            'history_weeks': data['history_weeks'],
            'cover_weeks': data['cover_weeks'],
            'safety_weeks': data['safety_weeks'],
            'min_usable_weeks': MIN_USABLE_WEEKS,
            'results': [_serialize_row(row) for row in rows],
        })
