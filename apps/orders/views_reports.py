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
"""
import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.orders.forms import InventoryReportForm
from apps.orders.models import Order, OrderItem

# Orders that moved product. Kept in sync with Order.RESOURCE_HOLDING_STATUSES.
COUNTED_STATUSES = ('confirmed', 'packing', 'completed')


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

    Args:
        date_range_choice: One of 'last_6_months', 'this_week', 'this_month',
            'last_month', 'this_year', 'custom'
        start_date: Custom start date (only used if date_range_choice is 'custom')
        end_date: Custom end date (only used if date_range_choice is 'custom')

    Returns:
        Tuple of (start_date, end_date) as date objects, both inclusive.
    """
    today = date.today()

    if date_range_choice == 'last_6_months':
        return _add_months(today, -6), today
    elif date_range_choice == 'this_week':
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
    else:
        # Default to the last 6 months (the planning horizon)
        return _add_months(today, -6), today


def _period_bucket(day, grouping):
    """
    Return (sort_key, label) for the bucket a date falls into.

    Weekly buckets start on Monday and are labelled with their start and
    end dates; monthly buckets are calendar months. With grouping='range'
    everything falls into a single unlabelled bucket.
    """
    if grouping == 'weekly':
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=6)
        return start.isoformat(), f"{start.isoformat()} to {end.isoformat()}"
    if grouping == 'monthly':
        start = day.replace(day=1)
        return start.isoformat(), start.strftime('%B %Y')
    return '', ''


def _local_order_date(order):
    """The local calendar date an order was placed on."""
    return timezone.localtime(order.order_date).date()


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
    start_datetime = timezone.make_aware(
        timezone.datetime.combine(start_date, timezone.datetime.min.time())
    )
    end_datetime = timezone.make_aware(
        timezone.datetime.combine(end_date, timezone.datetime.max.time())
    )

    items_qs = OrderItem.objects.filter(
        order__status__in=COUNTED_STATUSES,
        order__order_date__gte=start_datetime,
        order__order_date__lte=end_datetime,
    ).select_related(
        'product__category',
        'product__subcategory',
        'order__account__participant__program',
    )
    if program:
        items_qs = items_qs.filter(
            order__account__participant__program=program
        )

    item_totals = {}
    program_totals = {}
    for item in items_qs:
        order = item.order
        period_key, period_label = _period_bucket(
            _local_order_date(order), grouping
        )
        # Same cost rule as OrderItem.total_price().
        unit_price = (
            item.price_at_order if item.price_at_order is not None
            else item.price
        )
        line_total = unit_price * item.quantity

        item_key = (period_key, item.product_id)
        row = item_totals.get(item_key)
        if row is None:
            row = item_totals[item_key] = {
                'period_key': period_key,
                'period_label': period_label,
                'product_name': item.product.name,
                'category': (
                    item.product.category.name if item.product.category else ''
                ),
                'subcategory': (
                    item.product.subcategory.name
                    if item.product.subcategory else ''
                ),
                'quantity': 0,
                'total_cost': Decimal('0.00'),
            }
        row['quantity'] += item.quantity
        row['total_cost'] += line_total

        participant = order.account.participant
        program_name = (
            participant.program.name if participant.program else ''
        )
        cost_key = (period_key, program_name)
        cost_row = program_totals.get(cost_key)
        if cost_row is None:
            cost_row = program_totals[cost_key] = {
                'period_key': period_key,
                'period_label': period_label,
                'program_name': program_name,
                'total_cost': Decimal('0.00'),
            }
        cost_row['total_cost'] += line_total

    items = sorted(
        item_totals.values(),
        key=lambda r: (r['period_key'], -r['quantity'], r['product_name']),
    )
    program_costs = sorted(
        program_totals.values(),
        key=lambda r: (r['period_key'], r['program_name']),
    )
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
    ).select_related('account__participant')
    if program:
        orders_qs = orders_qs.filter(account__participant__program=program)

    participants_by_week = defaultdict(set)
    for order in orders_qs:
        order_day = _local_order_date(order)
        monday = order_day - timedelta(days=order_day.weekday())
        participants_by_week[monday].add(order.account.participant_id)

    participants_per_week = []
    monday = start_date - timedelta(days=start_date.weekday())
    last_monday = end_date - timedelta(days=end_date.weekday())
    while monday <= last_monday:
        participants_per_week.append({
            'week_start': monday,
            'week_end': monday + timedelta(days=6),
            'participant_count': len(participants_by_week.get(monday, ())),
        })
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
            return _generate_csv_report(report_data, start_date, end_date,
                                         grouping)

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
        line = [row['product_name'], row['category'], row['subcategory']]
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
        line = [row['program_name']]
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
    writer.writerow(['Week Start', 'Week End', 'Participants'])
    for row in report_data['participants_per_week']:
        writer.writerow([
            row['week_start'].isoformat(),
            row['week_end'].isoformat(),
            row['participant_count'],
        ])

    return response
