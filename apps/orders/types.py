"""Type definitions for FailedOrderAttempt JSON fields.

These TypedDicts document the exact shape stored in the cart_snapshot and
validation_errors JSONFields without adding any runtime overhead or requiring
serialisation boilerplate (they *are* plain dicts at runtime).
"""
from typing import Optional, TypedDict


class CartItem(TypedDict):
    """One line-item in a FailedOrderAttempt.cart_snapshot list."""
    product_id: int
    product_name: str
    quantity: int
    price: str  # Decimal serialised as string


class OrderError(TypedDict, total=False):
    """One entry in a FailedOrderAttempt.validation_errors list.

    ``type``       — error category: 'balance' | 'hygiene' | 'go_fresh' |
                     'limit' | 'window' | 'voucher' | 'validation' | 'general'
    ``message``    — human-readable description (always present)
    ``amount_over``— optional overage amount as a string, e.g. "12.50"
    """
    type: str       # required
    message: str    # required
    amount_over: Optional[str]  # optional
