# apps/orders/views_reports.py
"""Views for the inventory report (Issue #143).

Staff-only report of what was ordered over a date range: items ordered,
order cost by program, and distinct participants per week. Follows the
voucher redemption report pattern (apps/voucher/views_reports.py): an
admin view with a date-range form, on-screen tables, and a downloadable
export (CSV here, so the pantry team can work the numbers in a
spreadsheet).

Defaults (agreed with Liv Wilbraham, Nov 19, 2026):
- Only orders that actually moved product count: statuses confirmed,
  packing, and completed (the same set as Order.RESOURCE_HOLDING_STATUSES).
  Pending orders were never confirmed; cancelled orders had stock restored.
- The date used is Order.order_date (when the order was placed).
- Cost is quantity x price_at_order, falling back to the item's price
  field for rows created before the snapshot existed — the same rule as
  OrderItem.total_price().
- Program attribution uses the participant's *current* program. Order
  does not snapshot the program, so an order placed under a previous
  program reports under the participant's program today. Snapshotting
  the program on the order is a separate change if exact historical
  attribution is ever needed.
- Weeks start Monday. When the range starts or ends mid-week, that week
  is flagged as partial and labelled with the days actually counted, so
  a short first/last week is not mistaken for a quiet one.
- Aggregation happens in the database, bucketed by local (TIME_ZONE)
  calendar dates.
"""
import csv
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import Coalesce, TruncMonth, TruncWeek
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.orders.forms import InventoryReportForm
from apps.orders.models import Order, OrderItem

# Orders that moved product: the statuses that hold stock.
COUNTED_STATUSES = tuple(sorted(Order.RESOURCE_HOLDING_STATUSES))

CENTS = Decimal('0.01')

# Same cost rule as OrderItem.total_price(): the price snapshotted at order
# time, falling back to price for rows created before the snapshot existed.
LINE_TOTAL = ExpressionWrapper(
    Coalesce('price_at_order', 'price') * F('quantity'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


def _add_months(day, months):
    """Shift a date by a number of calendar months (clamping the day)."""
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    # Last day of the target month
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = (next_month - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def _get_date_range(date_range_choice, start_date=None, end_date=None):
    """
    Calculate start and end dates based on date range choice.

    "Today" is the local (TIME_ZONE) date, matching how orders are
    bucketed — not the server's date, which is UTC in production.

    Args:
        date_range_choice: One of 'last_6_months', 'this_week', 'this_month',
            'last_month', 'this_year', 'custom'
        start_date: Custom start date (only used if date_range_choice is 'custom')
        end_date: Custom end date (only used if date_range_choice is 'custom')

    Returns:
        Tuple of (start_date, end_date) as date objects, both inclusive.
    """
    today = timezone.localdate()

    if date_range_choice == 'this_week':
        # Start from Monday of current week
        start_of_week = today - timedelta(days=today.weekday())
        return start_of_week, today
    elif date_range_choice == 'this_month':
        return today.replace(day=1), today
    elif date_range_choice == 'last_month':
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_of_last_month.replace(day=1)
        return first_of_last_month, last_of_last_month
    elif date_range_choice == 'this_year':
        return date(today.year, 1, 1), today
    elif date_range_choice == 'custom':
        return start_date, end_date
    # 'last_6_months' and the fallback: the pantry's planning horizon.
    return _add_months(today, -6), today


def _week_info(monday, start_date, end_date):
    """Describe one Monday-start week, clipped to the report range.

    Returns a dict with the calendar week (week_start/week_end), the days
    actually counted (counted_from/counted_to), and is_partial when the
    range cuts the week short.
    """
    week_end = monday + timedelta(days=6)
    counted_from = max(monday, start_date)
    counted_to = min(week_end, end_date)
    return {
        'week_start': monday,
        'week_end': week_end,
        'counted_from': counted_from,
        'counted_to': counted_to,
        'is_partial': (counted_from, counted_to) != (monday, week_end),
    }


def _period_label(period, grouping, start_date, end_date):
    """Return (sort_key, label) for a truncated period value."""
    if grouping == 'weekly':
        info = _week_info(period, start_date, end_date)
        label = (
            f"{info['counted_from'].isoformat()} to "
            f"{info['counted_to'].isoformat()}"
        )
        if info['is_partial']:
            label += ' (partial week)'
        return period.isoformat(), label
    if grouping == 'monthly':
        return period.isoformat(), period.strftime('%B %Y')
    return '', ''


def _as_local_date(value):
    """Normalise a Trunc result (aware datetime or date) to a local date."""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def _get_inventory_data(start_date, end_date, program=None, grouping='range'):
    """
    Build the three report tables for a date range.

    Args:
        start_date: First date to include (inclusive)
        end_date: Last date to include (inclusive)
        program: Optional Program instance to filter by (the participant's
            current program — see module docstring)
        grouping: 'range', 'weekly', or 'monthly'. Applies to the items and
            cost-by-program tables; participants are always per week.

    Returns:
        Dict with 'items', 'program_costs', 'grand_total', and
        'participants_per_week'.
    """
    tz = timezone.get_current_timezone()
    start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
    end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

    items_qs = OrderItem.objects.filter(
        order__status__in=COUNTED_STATUSES,
        order__order_date__gte=start_datetime,
        order__order_date__lte=end_datetime,
    )
    if program:
        items_qs = items_qs.filter(
            order__account__participant__program=program
        )

    period_fields = []
    if grouping == 'weekly':
        items_qs = items_qs.annotate(
            period=TruncWeek('order__order_date', tzinfo=tz)
        )
        period_fields = ['period']
    elif grouping == 'monthly':
        items_qs = items_qs.annotate(
            period=TruncMonth('order__order_date', tzinfo=tz)
        )
        period_fields = ['period']

    def period_of(row):
        if not period_fields:
            return '', ''
        return _period_label(
            _as_local_date(row['period']), grouping, start_date, end_date
        )

    item_rows = (
        items_qs.order_by()
        .values(
            *period_fields,
            'product_id',
            'product__name',
            'product__category__name',
            'product__subcategory__name',
        )
        .annotate(total_qty=Sum('quantity'), total_cost=Sum(LINE_TOTAL))
    )
    items = []
    for row in item_rows:
        period_key, period_label = period_of(row)
        items.append({
            'period_key': period_key,
            'period_label': period_label,
            'product_name': row['product__name'],
            'category': row['product__category__name'] or '',
            'subcategory': row['product__subcategory__name'] or '',
            'quantity': row['total_qty'],
            'total_cost': Decimal(row['total_cost']).quantize(CENTS),
        })
    items.sort(
        key=lambda r: (r['period_key'], -r['quantity'], r['product_name'])
    )

    cost_rows = (
        items_qs.order_by()
        .values(*period_fields, 'order__account__participant__program__name')
        .annotate(total_cost=Sum(LINE_TOTAL))
    )
    program_costs = []
    for row in cost_rows:
        period_key, period_label = period_of(row)
        program_costs.append({
            'period_key': period_key,
            'period_label': period_label,
            'program_name': (
                row['order__account__participant__program__name'] or ''
            ),
            'total_cost': Decimal(row['total_cost']).quantize(CENTS),
        })
    program_costs.sort(key=lambda r: (r['period_key'], r['program_name']))
    grand_total = sum(
        (row['total_cost'] for row in program_costs), Decimal('0.00')
    )

    # Participants per week: distinct participants with at least one
    # counted order in each week overlapping the range. Weeks start
    # Monday; every week in the range is listed, including empty ones.
    orders_qs = Order.objects.filter(
        status__in=COUNTED_STATUSES,
        order_date__gte=start_datetime,
        order_date__lte=end_datetime,
    )
    if program:
        orders_qs = orders_qs.filter(account__participant__program=program)
    week_counts = (
        orders_qs.order_by()
        .annotate(week=TruncWeek('order_date', tzinfo=tz))
        .values('week')
        .annotate(n=Count('account__participant', distinct=True))
    )
    participants_by_week = defaultdict(int)
    for row in week_counts:
        participants_by_week[_as_local_date(row['week'])] += row['n']

    participants_per_week = []
    monday = start_date - timedelta(days=start_date.weekday())
    last_monday = end_date - timedelta(days=end_date.weekday())
    while monday <= last_monday:
        info = _week_info(monday, start_date, end_date)
        info['participant_count'] = participants_by_week.get(monday, 0)
        participants_per_week.append(info)
        monday += timedelta(days=7)

    return {
        'items': items,
        'program_costs': program_costs,
        'grand_total': grand_total,
        'participants_per_week': participants_per_week,
    }


@staff_member_required
def inventory_report(request):
    """
    View for the inventory report.

    Shows items ordered, order cost by program, and distinct participants
    per week for a selected date range, with an optional CSV export of
    exactly the tables shown on screen.
    """
    form = InventoryReportForm(request.GET or None)
    report_data = None
    date_range_display = None
    grouping = 'range'
    start_date = end_date = None

    if request.GET and form.is_valid():
        start_date, end_date = _get_date_range(
            form.cleaned_data['date_range'],
            form.cleaned_data.get('start_date'),
            form.cleaned_data.get('end_date'),
        )
        program = form.cleaned_data.get('program')
        grouping = form.cleaned_data.get('grouping', 'range')

        report_data = _get_inventory_data(
            start_date, end_date, program, grouping
        )
        date_range_display = (
            f"{start_date.strftime('%b %d, %Y')} - "
            f"{end_date.strftime('%b %d, %Y')}"
        )

        # Handle CSV export
        if 'export_csv' in request.GET:
            return _generate_csv_report(
                report_data, start_date, end_date, grouping
            )

    context = {
        'form': form,
        'report_data': report_data,
        'date_range_display': date_range_display,
        'grouping': grouping,
        'title': 'Inventory Report',
    }

    return render(
        request,
        'admin/orders/inventory_report.html',
        context
    )


def _csv_safe(value):
    """Neutralise spreadsheet formula injection in a text cell.

    Excel/Sheets treat cells starting with = + - @ (or tab/CR) as
    formulas; prefix those with an apostrophe so they display as text.
    """
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


def _generate_csv_report(report_data, start_date, end_date, grouping='range'):
    """
    Generate a CSV download of the same tables shown on screen.

    The CSV is built from the same report_data dict the template renders,
    so the exported numbers match the on-screen numbers exactly.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="inventory_report_'
        f'{start_date.isoformat()}_{end_date.isoformat()}.csv"'
    )
    writer = csv.writer(response)

    show_period = grouping != 'range'

    writer.writerow(['Items Ordered'])
    header = ['Product', 'Category', 'Subcategory']
    if show_period:
        header.append('Period')
    header += ['Quantity', 'Total Cost']
    writer.writerow(header)
    for row in report_data['items']:
        line = [
            _csv_safe(row['product_name']),
            _csv_safe(row['category']),
            _csv_safe(row['subcategory']),
        ]
        if show_period:
            line.append(row['period_label'])
        line += [row['quantity'], f"{row['total_cost']:.2f}"]
        writer.writerow(line)

    writer.writerow([])
    writer.writerow(['Order Cost by Program'])
    header = ['Program']
    if show_period:
        header.append('Period')
    header.append('Total Cost')
    writer.writerow(header)
    for row in report_data['program_costs']:
        line = [_csv_safe(row['program_name'])]
        if show_period:
            line.append(row['period_label'])
        line.append(f"{row['total_cost']:.2f}")
        writer.writerow(line)
    total_line = ['Grand Total']
    if show_period:
        total_line.append('')
    total_line.append(f"{report_data['grand_total']:.2f}")
    writer.writerow(total_line)

    writer.writerow([])
    writer.writerow(['Participants per Week'])
    writer.writerow(['Week Start', 'Week End', 'Participants', 'Note'])
    for row in report_data['participants_per_week']:
        note = ''
        if row['is_partial']:
            note = (
                f"Partial week: counts {row['counted_from'].isoformat()} "
                f"to {row['counted_to'].isoformat()} only"
            )
        writer.writerow([
            row['week_start'].isoformat(),
            row['week_end'].isoformat(),
            row['participant_count'],
            note,
        ])

    return response
