"""Periodic safety net: deactivate any active product at or below zero stock.

Order confirmation deactivates zero-stock products immediately
(Order._decrement_stock -> deactivate_out_of_stock_products). But stock
can reach zero through other queryset .update() paths that don't call
that helper (bulk imports, admin bulk actions, direct SQL) — those bypass
save()/signals just like the low-inventory threshold does, so a beat scan
is the only trigger that covers every mutation path. See
apps.pantry.tasks.low_inventory for the same reasoning applied to the
low-stock alert.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def deactivate_zero_stock_products():
    """Catch-all sweep — deactivates any active product left at zero stock."""
    from apps.pantry.utils.product_lifecycle import deactivate_out_of_stock_products

    deactivated = deactivate_out_of_stock_products()
    if deactivated:
        logger.info(
            "[ProductLifecycle] Deactivated %d product(s) at zero stock: %s",
            len(deactivated),
            ", ".join(name for _, name in deactivated),
        )
