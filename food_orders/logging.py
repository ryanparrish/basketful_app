# logging.py
from typing import Optional, Type
from .models import VoucherLog, Order, Voucher, Participant
from django.db.models import Model
def log_model(
    model: Type[Model],
    message: str,
    log_type: str = "INFO",
    order: Optional[Order] = None,
    voucher: Optional[Voucher] = None,
    participant: Optional[Participant] = None,
    balance_before: Optional[float] = None,
    balance_after: Optional[float] = None,
) -> Model:
    """
    Generic function to log an event to a specified model.

    Args:
        model: The Django model class to create the log in (VoucherLog or AccountLog).
        message: The log message.
        log_type: INFO, WARNING, ERROR, etc.
        order: Optional order associated with the log.
        voucher: Optional voucher associated with the log.
        participant: Optional participant associated with the log.
        balance_before: Optional balance before the event.
        balance_after: Optional balance after the event.

    Returns:
        The created log instance.
    """
    kwargs = {
        "message": message,
        "log_type": log_type,
        "participant": participant,
        "balance_before": balance_before,
        "balance_after": balance_after,
    }

    # Only include these if the model has them
    if hasattr(model, "order"):
        kwargs["order"] = order
    if hasattr(model, "voucher"):
        kwargs["voucher"] = voucher

    return model.objects.create(**kwargs)


# Convenience wrappers
def log_voucher(*args, **kwargs):
    """Log a voucher-related event."""
    return log_model(VoucherLog, *args, **kwargs)


