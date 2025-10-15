# utils.py
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from contextlib import contextmanager
import logging
from hashids import Hashids
from django.conf import settings

logger = logging.getLogger(__name__)

# --- Configuration ---
SALT = getattr(settings, "HASHIDS_SALT")
MIN_LENGTH = getattr(settings, "HASHIDS_MIN_LENGTH", 10)

if not SALT:
    raise ValueError("HASHIDS_SALT not configured in settings or environment")

# Initialize Hashids once
hashids = Hashids(salt=SALT, min_length=MIN_LENGTH)

# --- Utility functions ---
def encode_order_id(order_id: int) -> str:
    """Encode an integer order ID into a hashid string."""
    try:
        encoded = hashids.encode(order_id)
        logger.debug(f"Encoded order ID {order_id} -> {encoded}")
        return encoded
    except Exception as e:
        logger.exception(f"Failed to encode order ID {order_id}: {e}")
        raise

def decode_order_hash(hashid: str) -> int | None:
    """Decode a hashid string back to an integer order ID."""
    try:
        decoded = hashids.decode(hashid)
        order_id = decoded[0] if decoded else None
        logger.debug(f"Decoded order hash '{hashid}' -> {order_id}")
        return order_id
    except Exception as e:
        logger.exception(f"Failed to decode order hash '{hashid}': {e}")
        return None

def get_or_none(hashid: str, model_class):
    """
    Helper: Decode a hashid and return the model instance, or None if invalid.
    """
    order_id = decode_order_hash(hashid)
    if order_id is None:
        logger.warning(f"Invalid hashid provided: {hashid}")
        return None
    try:
        instance = model_class.objects.get(pk=order_id)
        logger.debug(f"Found {model_class.__name__} for hashid {hashid}: id={order_id}")
        return instance
    except model_class.DoesNotExist:
        logger.warning(f"{model_class.__name__} not found for hashid {hashid}")
        return None

# ============================================================
# PDF Generation Utility
# ============================================================

def generate_combined_order_pdf(combined_order) -> BytesIO:
    """
    Generate a PDF for a combined order and return a BytesIO buffer.
    """
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Start drawing
    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Combined Order #{combined_order.id}")
    y -= 20

    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Packed By: {combined_order.packed_by}")
    y -= 20
    p.drawString(50, y, f"Created At: {combined_order.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 30

    summary = combined_order.summarized_items_by_category()

    for category, products in summary.items():
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"{category}")
        y -= 20

        p.setFont("Helvetica", 12)
        for product, qty in products.items():
            p.drawString(70, y, f"{product}: {qty}")
            y -= 15
            if y < 100:
                p.showPage()
                y = height - 50

        y -= 10

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


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
