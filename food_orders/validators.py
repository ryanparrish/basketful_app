# validators.py
from django.core.exceptions import ValidationError
import logging
from .models import OrderValidationLog
from typing import List

logger = logging.getLogger(__name__)

def log_and_raise(participant, message, product=None, user=None):
    """
    Helper to log a validation message to the database and raise ValidationError.
    """
    OrderValidationLog.objects.create(
        participant=participant,
        product=product,
        message=message,
        user=user
    )
    logger.warning(f"[Validator] {message}")
    raise ValidationError(message)


def validate_order_items(
    items: List[OrderItemData], 
    participant, 
    account_balance, 
    user=None
):
    """
    Validate order items for limits, scoped totals, hygiene, and voucher balances.
    Accepts a list of OrderItemData dataclass instances.
    """
    if not participant:
        logger.debug("[Validator] No participant found — skipping validation.")
        return

    logger.debug(f"[Validator] Validating for Participant: {participant}")

    scoped_totals = {}
    hygiene_total = 0
    order_total = 0

    for item in items:
        product = item.product
        quantity = item.quantity

        if not product or not product.category:
            continue

        pm = getattr(product.category, "product_manager", None)
        if not pm or not pm.limit_scope or not pm.limit:
            continue

        scope = pm.limit_scope
        limit_quantity = pm.limit

        # Compute allowed quantity based on scope
        try:
            if scope == "per_adult":
                allowed = limit_quantity * participant.adults
            elif scope == "per_child":
                allowed = limit_quantity * participant.children
            elif scope == "per_infant":
                if participant.diaper_count == 0:
                    log_and_raise(
                        participant, 
                        "Limit is per infant, but participant has none.", 
                        user=user
                    )
                allowed = limit_quantity * participant.diaper_count
            elif scope == "per_household":
                allowed = limit_quantity * participant.household_size()
            elif scope == "per_order":
                allowed = limit_quantity
            else:
                continue  # unknown scope
        except Exception as e:
            logger.error(f"[Validator] Error computing allowed quantity: {e}")
            raise

        # Weight-based calculation
        use_weight = getattr(product, "weight_lbs", 0) > 0
        unit = "lbs" if use_weight else "items"
        value = quantity * getattr(product, "weight_lbs", 0) if use_weight else quantity

        # Track scoped totals
        key = f"{product.category.id}:{scope}:{unit}"
        scoped_totals.setdefault(key, 0)
        scoped_totals[key] += value

        logger.debug(
            f"[Validator] Product: {product.name}, Category: {product.category.name}, "
            f"Scope: {scope}, Limit: {allowed} {unit}, Current Total: {scoped_totals[key]} {unit}"
        )

        if scoped_totals[key] > allowed:
            msg = (
                f"Limit exceeded for {product.category.name} ({unit}, scope: {scope}): "
                f"{scoped_totals[key]} > allowed {allowed}"
            )
            log_and_raise(participant, msg, product=product, user=user)

        # Totals for balance checks
        line_total = product.price * quantity
        order_total += line_total
        if product.category.name.lower() == "hygiene":
            hygiene_total += line_total

    # Hygiene balance check
    if hygiene_total > account_balance.hygiene_balance:
        msg = (
            f"Hygiene items total ${hygiene_total:.2f}, exceeds hygiene balance "
            f"${account_balance.hygiene_balance:.2f}."
        )
        log_and_raise(participant, msg, user=user)

    # Voucher balance check
    if order_total > account_balance.voucher_balance:
        msg = (
            f"Order total ${order_total:.2f} exceeds available voucher balance "
            f"${account_balance.voucher_balance:.2f}."
        )
        log_and_raise(participant, msg, user=user)

    logger.debug("[Validator] Validation completed successfully.")
