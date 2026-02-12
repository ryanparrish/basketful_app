from decimal import Decimal
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def calculate_voucher_amount(voucher) -> Decimal:
    """
    Compute redeemable amount for a voucher.
    - Non-grocery vouchers return 0.
    - Consumed or expired vouchers return 0.
    - Returns base balance (multiplier is applied in balance calculations).
    """
    if voucher.voucher_type != "grocery":
        return Decimal("0.00")
    if voucher.state in ("consumed", "expired"):
        return Decimal("0.00")
    account = getattr(voucher, "account", None)
    if not account:
        return Decimal("0.00")

    base_balance = account.base_balance or Decimal("0.00")
    return base_balance
