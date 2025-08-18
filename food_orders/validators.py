# validators.py
from django.core.exceptions import ValidationError

def validate_order_items(forms, participant, account_balance):
    if not participant:
        print("[Validator] No participant found — skipping validation.")
        return

    print(f"[Validator] Validating for Participant: {participant}")
    scoped_totals = {}
    hygiene_total = 0
    order_total = 0

    for form in forms:
        if not form.cleaned_data or form.cleaned_data.get('DELETE', False):
            continue

        product = form.cleaned_data.get("product")
        quantity = form.cleaned_data.get("quantity", 0)

        if not product or not product.category:
            continue

        productmanager = getattr(product.category, 'product_manager', None)
        if not productmanager:
            continue

        scope = productmanager.limit_scope
        limit_quantity = productmanager.limit

        if not scope or not limit_quantity:
            continue

        if scope == "per_person":
            allowed = limit_quantity * participant.adults
        elif scope == "per_child":
            allowed = limit_quantity * participant.children
        elif scope == "per_infant":
            if participant.diaper_count == 0:
                raise ValidationError("Limit is per infant, but participant has none.")
            allowed = limit_quantity
        elif scope == "per_household":
            allowed = limit_quantity
        else:
            continue

        scoped_totals.setdefault(scope, 0)
        scoped_totals[scope] += quantity

        if scoped_totals[scope] > allowed:
            raise ValidationError(
                f"Limit exceeded for scope '{scope}': {scoped_totals[scope]} > allowed {allowed}"
            )

        line_total = product.price * quantity
        order_total += line_total

        if product.category.name.lower() == "hygiene":
            hygiene_total += line_total

    if hygiene_total > account_balance.hygiene_balance:
        raise ValidationError(
            f"Hygiene items total ${hygiene_total:.2f}, which exceeds hygiene balance of ${account_balance.hygiene_balance:.2f}."
        )

    if order_total > account_balance.voucher_balance:
        raise ValidationError(
            f"Order total ${order_total:.2f} exceeds available voucher balance of ${account_balance.voucher_balance:.2f}."
        )
