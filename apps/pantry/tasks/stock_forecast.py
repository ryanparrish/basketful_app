"""Stock forecast beat tasks (Issue #148).

``record_stock_snapshots`` keeps one row per product per local day with the
lowest stock seen and whether the product was ever inactive, so the
forecast can leave out weeks when a product couldn't be ordered. It runs
several times a day; stock is mutated through queryset ``.update()``
calls that no signal sees, so polling is the only way to observe it (the
same reasoning as ``low_inventory``).

``check_stock_forecast`` emails the low-inventory recipients a digest of
products newly projected to run out within the forecast alert window. It
follows the low-inventory alert's pattern: ``send_email_by_type`` with an
editable EmailType (``stock_forecast_alert``), and one alert per episode
via ``Product.forecast_alerted_at`` (claimed with a conditional UPDATE so
overlapping runs can't both send, cleared once the product recovers).
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

STOCK_FORECAST_EMAIL_TYPE = 'stock_forecast_alert'


def _display_date(day):
    """'Dec 12, 2026' (portable; no platform-specific strftime flags)."""
    return f"{day:%b} {day.day}, {day.year}"


@shared_task
def record_stock_snapshots():
    """Record today's lowest stock and availability for every product."""
    from apps.pantry.models import Product, ProductStockSnapshot

    today = timezone.localdate()
    existing = {
        snap.product_id: snap
        for snap in ProductStockSnapshot.objects.filter(date=today)
    }
    to_create, to_update = [], []
    for product in Product.objects.only('pk', 'quantity_in_stock', 'active'):
        snap = existing.get(product.pk)
        if snap is None:
            to_create.append(ProductStockSnapshot(
                product_id=product.pk, date=today,
                quantity_in_stock=product.quantity_in_stock,
                active=product.active,
            ))
            continue
        lowest = min(snap.quantity_in_stock, product.quantity_in_stock)
        active = snap.active and product.active
        if (lowest, active) != (snap.quantity_in_stock, snap.active):
            snap.quantity_in_stock, snap.active = lowest, active
            to_update.append(snap)
    # ignore_conflicts: a concurrent run may have created today's row first;
    # the next run folds in anything this one missed.
    ProductStockSnapshot.objects.bulk_create(to_create, ignore_conflicts=True)
    ProductStockSnapshot.objects.bulk_update(to_update, ['quantity_in_stock', 'active'])
    logger.info(
        "[StockForecast] Snapshots for %s: %d created, %d updated",
        today, len(to_create), len(to_update),
    )


@shared_task
def check_stock_forecast():
    """Email a digest of products newly forecast to run out soon."""
    from apps.account.tasks.email import send_email_by_type
    from apps.pantry.forecast import STATUS_INSUFFICIENT, compute_forecast
    from apps.pantry.models import LowInventoryAlertSettings, Product
    from apps.pantry.tasks.low_inventory import alert_recipients

    alert_settings = LowInventoryAlertSettings.get_settings()
    if not alert_settings.forecast_alerts_enabled:
        return

    alert_weeks = alert_settings.forecast_alert_weeks
    rows = compute_forecast()
    now = timezone.now()

    def at_risk(row):
        return (
            row['status'] != STATUS_INSUFFICIENT
            and row['weeks_left'] is not None
            and row['weeks_left'] <= alert_weeks
        )

    # Re-arm products that recovered: enough history and either no demand
    # or more than the alert window of stock left.
    recovered = [
        row['product_id'] for row in rows
        if row['status'] != STATUS_INSUFFICIENT and not at_risk(row)
    ]
    rearmed = Product.objects.filter(
        pk__in=recovered, forecast_alerted_at__isnull=False,
    ).update(forecast_alerted_at=None)
    if rearmed:
        logger.info("[StockForecast] Re-armed %d recovered product(s)", rearmed)

    newly_flagged = []
    for row in rows:
        if not at_risk(row):
            continue
        claimed = Product.objects.filter(
            pk=row['product_id'], forecast_alerted_at__isnull=True,
        ).update(forecast_alerted_at=now)
        if claimed:
            newly_flagged.append({
                'name': row['product_name'],
                'available': row['available'],
                'weekly_usage': row['weekly_usage'],
                'weeks_left': row['weeks_left'],
                'runout_date': _display_date(row['runout_date']),
                'suggested_reorder': row['suggested_reorder'],
            })

    if not newly_flagged:
        return

    recipients = alert_recipients(alert_settings)
    if not recipients.exists():
        logger.warning(
            "[StockForecast] %d product(s) newly at risk but no configured "
            "recipient has an emailable account; alert not delivered",
            len(newly_flagged),
        )
        return

    extra_context = {
        'products': newly_flagged,
        'product_count': len(newly_flagged),
        'alert_weeks': alert_weeks,
    }
    dispatched = 0
    for recipient in recipients:
        try:
            send_email_by_type.delay(
                recipient.pk, STOCK_FORECAST_EMAIL_TYPE,
                force=True, extra_context=extra_context,
            )
            dispatched += 1
        except Exception:
            logger.error(
                "[StockForecast] Failed to dispatch alert to user_id=%s",
                recipient.pk, exc_info=True,
            )
    logger.info(
        "[StockForecast] %d product(s) newly within %d week(s) of running "
        "out; dispatched %d alert email(s)",
        len(newly_flagged), alert_weeks, dispatched,
    )
