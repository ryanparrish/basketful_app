"""Stock forecast (Issue #148): how fast each product goes out, how long the
stock on hand will last, and how much to reorder.

Deliberately simple and explainable, with no ML. Every number can be
explained in one sentence.

For each product, over the last ``history_weeks`` *complete* Monday-start
weeks (local dates; the current week is excluded because it isn't over):

- **Weekly usage**: units on counted orders (confirmed, packing and
  completed, the same statuses as the inventory report, #143), averaged over
  the *usable* weeks and weighted toward recent weeks (weight 1 for the
  oldest week in the window up to ``history_weeks`` for last week).
- **Available**: ``quantity_in_stock`` minus units on *pending* orders.
  Confirmed, packing and completed orders have already decremented stock,
  so only pending ones are subtracted. Pantry-wide, not per program.
- **Weeks left**: available / weekly usage, and a projected run-out date.
- **Suggested reorder**: enough to cover ``cover_weeks + safety_weeks``
  of usage, minus what's available, rounded up. Doubles as the Feeding
  America order list.
- **Status**: ``critical`` (runs out within the safety window), ``low``
  (within the cover window), ``ok``, or ``insufficient_history``.

Usable weeks: a week with zero orders only means "no demand" if people
could order the product. A week is left out when:

1. a daily stock snapshot (ProductStockSnapshot) shows the product out of
   stock or inactive at some point that week, or
2. it falls before the product was created, or
3. there are no snapshots for it, the product is out of stock or inactive
   *now*, and it's part of the run of zero-order weeks leading up to now
   (the product most likely ran out). This bridges the gap until snapshot
   history builds up.

Products with fewer than ``MIN_USABLE_WEEKS`` usable weeks report
``insufficient_history`` instead of a made-up number.
"""
import math
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Max, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

DEFAULT_HISTORY_WEEKS = 12
DEFAULT_COVER_WEEKS = 4
DEFAULT_SAFETY_WEEKS = 1
MIN_USABLE_WEEKS = 4

STATUS_CRITICAL = 'critical'
STATUS_LOW = 'low'
STATUS_OK = 'ok'
STATUS_INSUFFICIENT = 'insufficient_history'
STATUS_CHOICES = [
    (STATUS_CRITICAL, 'Runs out within the safety window'),
    (STATUS_LOW, 'Runs out within the cover window'),
    (STATUS_OK, 'OK'),
    (STATUS_INSUFFICIENT, 'Not enough history'),
]
_STATUS_RANK = {STATUS_CRITICAL: 0, STATUS_LOW: 1, STATUS_OK: 2, STATUS_INSUFFICIENT: 3}


def _local_date(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def history_weeks_for(today, history_weeks):
    """Mondays of the last ``history_weeks`` complete weeks, oldest first."""
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=n) for n in range(history_weeks, 0, -1)]


def _explain(row, history_weeks):
    if row['status'] == STATUS_INSUFFICIENT:
        return (
            f"Only {row['usable_weeks']} usable week(s) of the last "
            f"{history_weeks}; needs {MIN_USABLE_WEEKS} to forecast."
        )
    usage = row['weekly_usage']
    text = (
        f"Averaged {usage:g}/week over {row['usable_weeks']} usable week(s) "
        f"of the last {history_weeks} (recent weeks count more)."
    )
    if row['weeks_left'] is None:
        return text + ' No recent demand.'
    if row['available'] <= 0:
        return text + ' Out of stock now.'
    return (
        text + f" {row['available']} available lasts about "
        f"{row['weeks_left']:g} week(s)."
    )


def compute_forecast(
    *,
    history_weeks=DEFAULT_HISTORY_WEEKS,
    cover_weeks=DEFAULT_COVER_WEEKS,
    safety_weeks=DEFAULT_SAFETY_WEEKS,
    product_ids=None,
    category=None,
    today=None,
):
    """Forecast rows, most urgent first. See the module docstring."""
    from apps.orders.models import Order, OrderItem
    from apps.pantry.models import Product, ProductStockSnapshot, StockMovement

    today = today or timezone.localdate()
    tz = timezone.get_current_timezone()
    weeks = history_weeks_for(today, history_weeks)
    window_start = weeks[0]
    window_end = weeks[-1] + timedelta(days=6)
    start_dt = timezone.make_aware(datetime.combine(window_start, time.min))
    end_dt = timezone.make_aware(datetime.combine(window_end, time.max))

    products = Product.objects.select_related('category').order_by('name')
    if product_ids is not None:
        products = products.filter(pk__in=product_ids)
    if category is not None:
        products = products.filter(category=category)

    counted = tuple(Order.RESOURCE_HOLDING_STATUSES)
    usage = defaultdict(int)  # (product_id, monday) -> units
    usage_rows = (
        OrderItem.objects.filter(
            order__status__in=counted,
            order__order_date__gte=start_dt,
            order__order_date__lte=end_dt,
            product__in=products,
        )
        .order_by()
        .annotate(week=TruncWeek('order__order_date', tzinfo=tz))
        .values('product_id', 'week')
        .annotate(units=Sum('quantity'))
    )
    for row in usage_rows:
        usage[(row['product_id'], _local_date(row['week']))] += row['units']

    pending = dict(
        OrderItem.objects.filter(order__status='pending', product__in=products)
        .order_by()
        .values('product_id')
        .annotate(units=Sum('quantity'))
        .values_list('product_id', 'units')
    )

    covered = set()       # (product_id, monday) with any snapshot
    unavailable = set()   # (product_id, monday) out of stock/inactive at some point
    for snap in ProductStockSnapshot.objects.filter(
        product__in=products, date__gte=window_start, date__lte=window_end,
    ).values('product_id', 'date', 'quantity_in_stock', 'active'):
        monday = snap['date'] - timedelta(days=snap['date'].weekday())
        key = (snap['product_id'], monday)
        covered.add(key)
        if not snap['active'] or snap['quantity_in_stock'] <= 0:
            unavailable.add(key)

    last_received = dict(
        StockMovement.objects.filter(product__in=products, quantity_change__gt=0)
        .order_by()
        .values('product_id')
        .annotate(last=Max('created_at'))
        .values_list('product_id', 'last')
    )

    rows = []
    for product in products:
        pid = product.pk
        units_in_window = sum(usage.get((pid, m), 0) for m in weeks)
        stock = product.quantity_in_stock
        # Skip discontinued products: inactive, nothing on hand, no demand.
        if not product.active and stock <= 0 and units_in_window == 0 and product_ids is None:
            continue

        created_monday = None
        if product.created_at:
            created = _local_date(product.created_at)
            created_monday = created - timedelta(days=created.weekday())
        unavailable_now = (not product.active) or stock <= 0

        history = []
        in_trailing_gap = True
        for monday in reversed(weeks):
            units = usage.get((pid, monday), 0)
            key = (pid, monday)
            if created_monday and monday < created_monday:
                usable, reason = False, 'before the product existed'
            elif key in covered:
                usable = key not in unavailable
                reason = '' if usable else 'out of stock or inactive that week'
            elif in_trailing_gap and unavailable_now and units == 0:
                usable, reason = False, 'likely out of stock: no orders since it ran out'
            else:
                usable, reason = True, ''
            if units > 0 or (key in covered and usable):
                in_trailing_gap = False
            history.append({
                'week_start': monday,
                'units': units,
                'usable': usable,
                'excluded_reason': reason,
            })
        history.reverse()  # oldest first

        weighted_sum = weight_total = 0
        usable_weeks = 0
        for position, week in enumerate(history, start=1):
            if week['usable']:
                weighted_sum += position * week['units']
                weight_total += position
                usable_weeks += 1

        available = stock - pending.get(pid, 0)
        row = {
            'product_id': pid,
            'product_name': product.name,
            'category': product.category.name if product.category else '',
            'active': product.active,
            'quantity_in_stock': stock,
            'pending_units': pending.get(pid, 0),
            'available': available,
            'usable_weeks': usable_weeks,
            'weekly_usage': None,
            'weeks_left': None,
            'runout_date': None,
            'suggested_reorder': None,
            'status': STATUS_INSUFFICIENT,
            'last_received_at': last_received.get(pid),
            'history': history,
        }
        if usable_weeks >= MIN_USABLE_WEEKS:
            weekly = round(weighted_sum / weight_total, 1) if weight_total else 0.0
            row['weekly_usage'] = weekly
            row['suggested_reorder'] = max(
                0, math.ceil(weekly * (cover_weeks + safety_weeks) - available)
            )
            if weekly > 0:
                weeks_left = round(max(available, 0) / weekly, 1)
                row['weeks_left'] = weeks_left
                row['runout_date'] = today + timedelta(days=math.floor(weeks_left * 7))
                if weeks_left <= safety_weeks:
                    row['status'] = STATUS_CRITICAL
                elif weeks_left <= cover_weeks:
                    row['status'] = STATUS_LOW
                else:
                    row['status'] = STATUS_OK
            else:
                row['status'] = STATUS_OK
        row['explanation'] = _explain(row, history_weeks)
        rows.append(row)

    rows.sort(key=lambda r: (
        _STATUS_RANK[r['status']],
        r['weeks_left'] if r['weeks_left'] is not None else math.inf,
        r['product_name'],
    ))
    return rows


def forecast_by_product(product_ids, **kwargs):
    """{product_id: row} for a set of products (e.g. one page of a list)."""
    return {row['product_id']: row for row in compute_forecast(product_ids=product_ids, **kwargs)}


__all__ = [
    'DEFAULT_HISTORY_WEEKS', 'DEFAULT_COVER_WEEKS', 'DEFAULT_SAFETY_WEEKS',
    'MIN_USABLE_WEEKS', 'STATUS_CHOICES', 'STATUS_CRITICAL', 'STATUS_LOW',
    'STATUS_OK', 'STATUS_INSUFFICIENT', 'compute_forecast',
    'forecast_by_product', 'history_weeks_for',
]
