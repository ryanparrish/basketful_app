# food_orders/tests/test_order_validation.py

"""
Test helper functions for order validation in the food_orders app.

Includes voucher logging utilities with a shared logger.
"""

from food_orders.models import Voucher

_logged_once = False  # Module-level flag to print header only once per test run

def log_vouchers_for_account(account, context: str = "", order=None):
    """
    Logs all vouchers associated with an account, including active/inactive
    status and total balances. Useful for debugging voucher logic in tests.

    Args:
        account (AccountBalance): The participant's account
        context (str): Optional context string
        order (Order): Optional order to include total price in log

    Returns:
        dict: Contains lists of active and inactive vouchers and total active balance
    """
    global _logged_once

    # --- Print header once per test run ---
    if not _logged_once:
        test_logger.info("\n === Starting Voucher Logging ===\n")
        _logged_once = True

    vouchers = Voucher.objects.filter(account=account)
    active_vouchers = [v for v in vouchers if v.active]
    inactive_vouchers = [v for v in vouchers if not v.active]

    # --- Log context ---
    test_logger.info(f"\n--- Voucher log: {context} ---")

    # --- Log order info if provided ---
    if order is not None:
        total_price = getattr(order, "_test_price", getattr(order, "total_price", "N/A"))
        test_logger.info(f"Order ID: {getattr(order, 'id', 'unsaved')}, Total Price={total_price}")

    # --- Log individual voucher details ---
    for v in vouchers:
        test_logger.info(
            f"Voucher ID: {v.id}, Type: {v.voucher_type}, "
            f"Amount: {v.voucher_amnt}, Active: {v.active}"
        )

    # --- Log summary ---
    total_balance = sum(v.voucher_amnt for v in active_vouchers)
    test_logger.info(
        f"Summary: Active={len(active_vouchers)}, Inactive={len(inactive_vouchers)}, "
        f"Total Active Balance={total_balance}\n"
    )

    return {"active": active_vouchers, "inactive": inactive_vouchers, "total_balance": total_balance}
