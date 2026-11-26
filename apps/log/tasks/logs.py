# food_orders/taskslogs.py
"""Tasks for logging voucher applications and polling Mailgun delivery status."""
# Standard library imports
import logging
from datetime import timedelta
# Third-party imports
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
# First-party imports
from apps.orders.models import Order 
from apps.voucher.models import Voucher
from apps.log.models import VoucherLog, EmailLog
from apps.account.models import Participant

# Create a logger for this module
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)  # or DEBUG if you want more detail

# Optional: add a console handler if one doesn’t exist
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

@shared_task
def log_voucher_application_task(
    order_id, voucher_id, participant_id, applied_amount, remaining
):
    """
    Task to log the application of a voucher to an order.
    """
    # Fetch related objects
    # If Order does not have a default manager, use the appropriate manager or method
    order = Order.objects.get(id=order_id)  # Ensure Order is a Django model
    voucher = Voucher.objects.get(id=voucher_id)
    participant = Participant.objects.get(id=participant_id)

    # Ensure numeric values are never None
    applied_amount = float(applied_amount or 0.0)
    remaining = float(remaining or 0.0)

    # Determine note type - compare applied to voucher amount
    voucher_amnt = float(voucher.voucher_amnt)
    note_type = "Fully used" if applied_amount >= voucher_amnt else "Partially used"

    # Build log message
    message = (
        f"{note_type} voucher {voucher.id} "
        f"for ${applied_amount:.2f}, remaining amount needed: ${remaining:.2f}"
    )

    # Create log entry
    VoucherLog.objects.create(
        order=order,
        voucher=voucher,
        participant=participant,
        applied_amount=applied_amount,
        remaining=remaining,
        message=message,
        log_type=VoucherLog.INFO,
    )


# ---------------------------------------------------------------------------
# Mailgun delivery status polling
# ---------------------------------------------------------------------------

# Mailgun event names that map directly to our delivery_status field
_VALID_DELIVERY_STATUSES = {"delivered", "bounced", "complained", "unsubscribed", "failed"}

# How far back to consider logs still worth polling (Mailgun retains events ~30 days)
_POLL_WINDOW_DAYS = 7

# Skip a log if we polled it within this window (avoid hammering the API)
_RECHECK_COOLDOWN_MINUTES = 25


@shared_task
def sync_mailgun_delivery_status():
    """
    Poll the Mailgun Events API for every EmailLog that:
    - Has a message_id (was successfully handed to Mailgun)
    - Still has delivery_status="unknown"
    - Was sent within the last _POLL_WINDOW_DAYS days
    - Has not been checked within the last _RECHECK_COOLDOWN_MINUTES minutes

    Writes the resolved status and delivery_checked_at back to the row.
    Logs without a message_id (local send failures, dev environment) are skipped.
    """
    anymail_settings = getattr(settings, "ANYMAIL", {})
    api_key = anymail_settings.get("MAILGUN_API_KEY")
    domain = anymail_settings.get("MAILGUN_SENDER_DOMAIN")

    if not api_key or not domain:
        logger.warning(
            "[MailgunSync] Skipped — MAILGUN_API_KEY or MAILGUN_SENDER_DOMAIN not configured"
        )
        return

    now = timezone.now()
    cutoff = now - timedelta(days=_POLL_WINDOW_DAYS)
    cooldown = now - timedelta(minutes=_RECHECK_COOLDOWN_MINUTES)

    pending = (
        EmailLog.objects
        .filter(
            delivery_status="unknown",
            sent_at__gte=cutoff,
        )
        .exclude(message_id__isnull=True)
        .exclude(message_id="")
        .exclude(delivery_checked_at__gte=cooldown)
        .order_by("sent_at")
    )

    total = pending.count()
    logger.info("[MailgunSync] Checking %s pending email log(s)", total)

    resolved = 0
    for log in pending:
        try:
            resp = requests.get(
                f"https://api.mailgun.net/v3/{domain}/events",
                auth=("api", api_key),
                params={"message-id": log.message_id, "limit": 5},
                timeout=10,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])

            # Walk events newest-first; prefer a terminal status over "accepted"
            resolved_status = "unknown"
            for item in items:
                event = item.get("event", "")
                if event in _VALID_DELIVERY_STATUSES:
                    resolved_status = event
                    break  # highest-priority event found

            log.delivery_status = resolved_status
            log.delivery_checked_at = now
            log.save(update_fields=["delivery_status", "delivery_checked_at"])

            if resolved_status != "unknown":
                resolved += 1
                logger.info(
                    "[MailgunSync] log_id=%s message_id=%s => %s",
                    log.id, log.message_id, resolved_status
                )

        except requests.RequestException as exc:
            logger.warning(
                "[MailgunSync] API error for log_id=%s: %s", log.id, exc
            )
            # Still stamp delivery_checked_at so we don't hammer on API errors
            log.delivery_checked_at = now
            log.save(update_fields=["delivery_checked_at"])

    logger.info(
        "[MailgunSync] Done. %s/%s logs resolved to a terminal status.", resolved, total
    )
