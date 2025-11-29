
import logging
from account.models import Participant
from .models import VoucherLog
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class VoucherLogger:
    """Helper to log voucher events to DB and console."""
    @staticmethod
    def debug(participant: Participant, message: str, voucher=None, user=None):
        logger.debug("[Voucher DEBUG] %s", message)
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="DEBUG",
            user=user
        )

    @staticmethod
    def error(
        participant: Participant, 
        message: str, 
        voucher=None, 
        user=None, 
        raise_exception=False
    ):
        """Log an error message and optionally raise a ValidationError."""
        logger.error("[Voucher Log ERROR] %s", message)
        VoucherLog.objects.create(
            participant=participant,
            voucher=voucher,
            message=message,
            log_type="ERROR",
            user=user
        )
        if raise_exception:
            raise ValidationError(message)
    