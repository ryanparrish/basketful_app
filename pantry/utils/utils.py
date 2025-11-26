# utils.py
"""Utility functions for food orders."""
from contextlib import contextmanager
# ============================================================
# PDF Generation Utility
# ============================================================


@contextmanager
def skip_signals(instance):
    """
    Temporarily sets a flag on a model instance to skip signal handlers.
    """
    instance._skip_signal = True   # setup: mark it
    try:
        yield instance             # run the block inside the `with` statement
    finally:
        instance._skip_signal = False  # teardown: reset the flag
