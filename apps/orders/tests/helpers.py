"""Helpers for tests that place orders through the API or web pages."""
from core.models import ProgramOrderWindow


def no_order_window(program):
    """Let a program take orders at any time.

    Placing an order checks the program's order window first (M15), which
    would reject the order before whatever a test is checking. A program
    with its window turned off is a real configuration. The window itself
    is tested in apps/orders/tests/test_bug_repros_2026_10_16.py
    (test_m15_order_window_enforced_on_create).
    """
    ProgramOrderWindow.objects.update_or_create(
        program=program, defaults={'enabled': False}
    )
