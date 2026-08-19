"""Zero-stock deactivation (Issue #97).

Deliberately never reactivates a product on restock — a product can hit
zero and get deactivated for reasons unrelated to a temporary stockout
(e.g. staff discontinuing it), so bringing it back into the catalog is
left to an explicit staff action.
"""
import logging

logger = logging.getLogger(__name__)


def deactivate_out_of_stock_products(product_ids=None):
    """
    Deactivate every active product whose stock is at or below zero.

    Pass `product_ids` to scope the check to specific products right after
    they were touched (e.g. by Order._decrement_stock); omit it to sweep
    every product, as a safety net for mutation paths that don't call this
    directly (bulk edits, imports, other queryset .update() calls).

    Returns the list of (id, name) tuples for products just deactivated.
    """
    from apps.pantry.models import Product

    queryset = Product.objects.filter(active=True, quantity_in_stock__lte=0)
    if product_ids is not None:
        queryset = queryset.filter(pk__in=product_ids)

    deactivated = list(queryset.values_list('id', 'name'))
    if not deactivated:
        return []

    Product.objects.filter(pk__in=[pid for pid, _ in deactivated]).update(active=False)
    return deactivated
