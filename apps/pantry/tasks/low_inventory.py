"""Periodic low-inventory scan.

Stock is mutated via queryset ``.update()`` (F-expressions in
``Order._decrement_stock`` and the DRF Product serializer), so no
``save()``/signal hook can observe threshold crossings — a beat scan is
the only trigger that covers every mutation path.

Alert state lives in ``Product.low_stock_alerted_at``: set when a low
product is alerted, cleared once its stock recovers above the threshold.
The per-row conditional UPDATE that sets it doubles as the concurrency
guard — overlapping beat ticks cannot both claim the same product.
"""
import logging

from celery import shared_task
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_low_inventory():
    """Alert configured recipients about products newly at/below the threshold."""
    from django.contrib.auth import get_user_model

    from apps.account.tasks.email import send_email_by_type
    from apps.pantry.models import LowInventoryAlertSettings, Product

    alert_settings = LowInventoryAlertSettings.get_settings()
    if not alert_settings.enabled:
        return

    threshold = alert_settings.threshold
    now = timezone.now()

    rearmed_count = Product.objects.filter(
        low_stock_alerted_at__isnull=False,
        quantity_in_stock__gt=threshold,
    ).update(low_stock_alerted_at=None)
    if rearmed_count:
        logger.info(
            "[LowInventory] Re-armed %d product(s) that recovered above threshold %d",
            rearmed_count, threshold,
        )

    candidate_products = Product.objects.filter(
        active=True,
        quantity_in_stock__lte=threshold,
        low_stock_alerted_at__isnull=True,
    ).order_by('name')

    newly_low_products = []
    for product in candidate_products:
        claimed = Product.objects.filter(
            pk=product.pk,
            low_stock_alerted_at__isnull=True,
        ).update(low_stock_alerted_at=now)
        if claimed:
            newly_low_products.append({
                'name': product.name,
                'quantity_in_stock': product.quantity_in_stock,
            })

    if not newly_low_products:
        return

    User = get_user_model()
    recipients = (
        User.objects
        .filter(
            models.Q(groups__in=alert_settings.notify_groups.all())
            | models.Q(pk__in=alert_settings.notify_users.all())
        )
        .filter(is_active=True)
        .exclude(email='')
        .distinct()
    )
    if not recipients.exists():
        logger.warning(
            "[LowInventory] %d product(s) newly low but no configured "
            "recipient (group or user) has an emailable account — "
            "alert not delivered",
            len(newly_low_products),
        )
        return

    extra_context = {
        'products': newly_low_products,
        'threshold': threshold,
        'product_count': len(newly_low_products),
    }
    dispatched_count = 0
    for recipient in recipients:
        try:
            send_email_by_type.delay(
                recipient.pk,
                'low_inventory_alert',
                force=True,
                extra_context=extra_context,
            )
            dispatched_count += 1
        except Exception:
            logger.error(
                "[LowInventory] Failed to dispatch alert to user_id=%s",
                recipient.pk, exc_info=True,
            )

    logger.info(
        "[LowInventory] %d product(s) newly at/below threshold %d — "
        "dispatched %d alert email(s)",
        len(newly_low_products), threshold, dispatched_count,
    )
