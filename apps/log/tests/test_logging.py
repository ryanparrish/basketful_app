# food_orders/tests/test_order_validation.py

"""
Test helper functions for order validation in the food_orders app.

Provides utilities to inspect vouchers for a given account with clean console logging.
"""

from apps.voucher.models import Voucher

_logged_once = False  # Module-level flag to print header only once per test run


def log_vouchers_for_account(account, context: str = "", order=None):
    """
    Logs all vouchers associated with an account in a clean, readable format.

    Args:
        account (AccountBalance): The participant's account
        context (str): Optional context string
        order (Order): Optional order to include total price in log

    Returns:
        dict: Contains lists of active and inactive vouchers and total active balance
    """
    global _logged_once

    vouchers = Voucher.objects.filter(account=account)
    active_vouchers = [v for v in vouchers if v.active]
    inactive_vouchers = [v for v in vouchers if not v.active]

    total_balance = sum(v.voucher_amnt for v in active_vouchers)

    # --- Print header once per test run ---
    if not _logged_once:
        print("\n" + "=" * 40)
        print("=== Starting Voucher Logging ===")
        print("=" * 40 + "\n")
        _logged_once = True

    # --- Context info ---
    if context or order:
        print(f"--- Voucher Log: {context} ---")
        if order is not None:
            total_price = getattr(order, "_test_price", getattr(order, "total_price", "N/A"))
            print(f"Order ID: {getattr(order, 'id', 'unsaved')}, Total Price={total_price}")

    # --- Individual voucher details ---
    for v in vouchers:
        print(
            f"[Voucher ID: {v.id}] Type: {v.voucher_type} | "
            f"Amount: {v.voucher_amnt} | Active: {v.active}"
        )

    # --- Summary ---
    print(f"Summary: Active={len(active_vouchers)}, Inactive={len(inactive_vouchers)}, "
          f"Total Active Balance={total_balance}\n")

    return {
        "active": active_vouchers,
        "inactive": inactive_vouchers,
        "total_balance": total_balance
    }
