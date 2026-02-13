# orders/utils/order_services.py
"""Utility services for Order processing."""
# Standard library imports  
import logging
import hashlib
import json
import time
from io import BytesIO
from datetime import datetime, timedelta
from contextlib import contextmanager
from hashids import Hashids
# Django imports
from django.conf import settings
from django.core.cache import cache
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

logger = logging.getLogger(__name__)

# --- Configuration ---
SALT = getattr(settings, "HASHIDS_SALT")
MIN_LENGTH = getattr(settings, "HASHIDS_MIN_LENGTH", 10)

if not SALT:
    raise ValueError("HASHIDS_SALT not configured in settings or environment")

# Initialize Hashids once
hashids = Hashids(salt=SALT, min_length=MIN_LENGTH)

# --- Idempotency and Distributed Lock Utilities ---

def generate_idempotency_key(participant_id: int, cart_items: list) -> str:
    """
    Generate idempotency key from participant + cart + timestamp (minute precision).
    
    Args:
        participant_id: The participant's ID
        cart_items: List of dicts with 'product_id' and 'quantity'
    
    Returns:
        SHA256 hash string to use as idempotency key
    """
    # Sort cart items by product_id for consistency
    sorted_cart = sorted(cart_items, key=lambda x: x.get('product_id', 0))
    cart_str = json.dumps(sorted_cart, sort_keys=True)
    
    # Use minute-level timestamp for 5-minute window
    timestamp_minute = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Generate hash
    key_data = f"{participant_id}:{cart_str}:{timestamp_minute}"
    return hashlib.sha256(key_data.encode()).hexdigest()


def generate_cart_hash(cart_items: list) -> str:
    """
    Generate hash of cart contents for duplicate detection.
    
    Args:
        cart_items: List of dicts with 'product_id' and 'quantity'
    
    Returns:
        SHA256 hash of cart contents
    """
    sorted_cart = sorted(cart_items, key=lambda x: x.get('product_id', 0))
    cart_str = json.dumps(sorted_cart, sort_keys=True)
    return hashlib.sha256(cart_str.encode()).hexdigest()


@contextmanager
def distributed_order_lock(participant_id: int, timeout: int = 10):
    """
    Context manager for Redis-based distributed lock with fallback.
    
    Args:
        participant_id: The participant's ID
        timeout: Lock timeout in seconds
    
    Yields:
        bool: True if lock acquired, False otherwise
    
    Example:
        with distributed_order_lock(participant.id) as acquired:
            if acquired:
                # Process order
                pass
            else:
                # Handle concurrent request
                pass
    """
    lock_key = f"order_lock:participant:{participant_id}"
    lock_acquired = False
    
    try:
        # Try to acquire lock with Redis
        lock_acquired = cache.add(lock_key, "locked", timeout)
        
        if not lock_acquired:
            logger.warning(
                f"Failed to acquire order lock for participant {participant_id}. "
                "Possible concurrent order submission."
            )
        
        yield lock_acquired
        
    except Exception as e:
        # Redis unavailable - log warning but allow through (graceful degradation)
        logger.warning(
            f"Redis unavailable for distributed lock (participant {participant_id}): {e}. "
            "Allowing request to proceed without lock."
        )
        yield True  # Allow through when Redis is down
        
    finally:
        # Release lock if we acquired it
        if lock_acquired:
            try:
                cache.delete(lock_key)
            except Exception as e:
                logger.error(f"Failed to release lock for participant {participant_id}: {e}")


def check_duplicate_submission(idempotency_key: str, ttl_seconds: int = 300) -> bool:
    """
    Check if this submission is a duplicate within the TTL window.
    
    Args:
        idempotency_key: The idempotency key to check
        ttl_seconds: Time-to-live in seconds (default: 5 minutes)
    
    Returns:
        bool: True if duplicate, False if new submission
    """
    cache_key = f"order_idempotency:{idempotency_key}"
    
    try:
        # Check if key exists
        if cache.get(cache_key):
            logger.warning(f"Duplicate order submission detected: {idempotency_key}")
            return True
        
        # Mark as submitted
        cache.set(cache_key, "submitted", ttl_seconds)
        return False
        
    except Exception as e:
        # Redis unavailable - log warning but allow through
        logger.warning(
            f"Redis unavailable for idempotency check: {e}. "
            "Allowing request to proceed without duplicate detection."
        )
        return False  # Treat as new when Redis is down

# --- Utility functions ---


def decode_order_hash(hashid: str) -> int | None:
    """Decode a hashid string back to an integer order ID."""
    try:
        decoded = hashids.decode(hashid)
        order_id = decoded[0] if decoded else None
        logger.debug(f"Decoded order hash '{hashid}' -> {order_id}")
        return order_id
    except (ValueError, TypeError) as e:
        logger.exception("Failed to decode order hash '%s': %s", hashid, e)
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
    

def encode_order_id(order_id: int) -> str:
    """Encode an integer order ID into a hashid string."""
    try:
        encoded = hashids.encode(order_id)
        logger.debug(f"Encoded order ID {order_id} -> {encoded}")
        return encoded
    except Exception as e:
        logger.exception(f"Failed to encode order ID {order_id}: {e}")
        raise


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


# --- Packing List PDF Helper Functions ---

# Page layout constants
USABLE_HEIGHT = 650  # Letter height minus top/bottom margins
TOP_MARGIN = 50
BOTTOM_MARGIN = 80  # Leave room for page numbers
PAGE_NUMBER_Y = 30


def _calculate_order_height(item_count: int, font_size: int) -> int:
    """
    Calculate the vertical space needed for an order.
    
    Args:
        item_count: Number of items in the order
        font_size: Font size for items (12 or 10)
        
    Returns:
        Height in points needed for the order
    """
    line_spacing = font_size + 3
    header_height = 40  # Customer header + spacing
    items_height = item_count * line_spacing
    footer_height = 25  # Separator line + spacing
    return header_height + items_height + footer_height


def _draw_page_number(p, current_page: int, total_pages: int, width: float):
    """Draw centered page number at bottom of page."""
    p.setFont("Helvetica", 9)
    text = f"Page {current_page} of {total_pages}"
    text_width = p.stringWidth(text, "Helvetica", 9)
    p.drawString((width - text_width) / 2, PAGE_NUMBER_Y, text)


def _count_summary_pages(summarized_data: dict, usable_height: int) -> int:
    """
    Count how many pages the summary section will need.
    
    Args:
        summarized_data: Dict of {category: {product: qty}}
        usable_height: Available height per page for summary content
        
    Returns:
        Number of pages needed for summary
    """
    if not summarized_data:
        return 1
    
    # Header takes ~180pt (title, program, packer, etc.)
    # Summary title takes ~30pt
    first_page_available = usable_height - 210
    continuation_available = usable_height - 50  # Just "SUMMARY (continued)" header
    
    total_items = 0
    for category, products in summarized_data.items():
        total_items += 1  # Category header
        total_items += len(products)  # Products
    
    line_height = 15
    total_height = total_items * line_height + 50  # Plus signature line
    
    if total_height <= first_page_available:
        return 1
    
    remaining = total_height - first_page_available
    extra_pages = (remaining + continuation_available - 1) // continuation_available
    return 1 + extra_pages


def generate_packing_list_pdf(packing_list) -> BytesIO:
    """
    Generate a PDF packing list for a specific packer.
    
    Layout:
    - Each order on its own page with adaptive font sizing (12pt → 10pt)
    - Summary page at end with header info
    - Page numbers "Page X of Y" on all pages
    
    Uses customer numbers only for privacy (no participant names).
    
    Args:
        packing_list: PackingList instance with orders and packer assignment
        
    Returns:
        BytesIO buffer containing the PDF
    """
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    combined_order = packing_list.combined_order
    packer = packing_list.packer
    orders = list(packing_list.orders.all().select_related(
        'account__participant'
    ).prefetch_related('items__product'))
    
    summarized_data = packing_list.summarized_data or {}
    
    # Pre-calculate total pages
    # Each order gets its own page; check if any overflow at size 10
    order_pages = 0
    order_info = []  # [(order, item_count, font_size, needs_overflow)]
    
    for order in orders:
        item_count = order.items.count()
        height_at_12 = _calculate_order_height(item_count, 12)
        height_at_10 = _calculate_order_height(item_count, 10)
        
        if height_at_12 <= USABLE_HEIGHT:
            order_info.append((order, item_count, 12, False))
            order_pages += 1
        elif height_at_10 <= USABLE_HEIGHT:
            order_info.append((order, item_count, 10, False))
            order_pages += 1
        else:
            # Will overflow - calculate extra pages needed at size 10
            order_info.append((order, item_count, 10, True))
            items_first_page = (USABLE_HEIGHT - 40) // 13  # 13pt line spacing for size 10
            remaining_items = item_count - items_first_page
            continuation_capacity = (USABLE_HEIGHT - 50) // 13
            extra_pages = (remaining_items + continuation_capacity - 1) // continuation_capacity
            order_pages += 1 + extra_pages
    
    summary_pages = _count_summary_pages(summarized_data, USABLE_HEIGHT)
    total_pages = order_pages + summary_pages
    
    current_page = 0
    
    # Render each order on its own page
    for order, item_count, font_size, needs_overflow in order_info:
        current_page += 1
        y = height - TOP_MARGIN
        
        # Get customer number
        participant = order.account.participant if order.account else None
        customer_number = getattr(participant, 'customer_number', 'N/A') if participant else 'N/A'
        
        # Order header
        p.setFont("Helvetica-Bold", font_size + 2)
        p.drawString(50, y, f"Customer #{customer_number}")
        y -= font_size + 8
        
        # Separator line under header
        p.line(50, y, width - 50, y)
        y -= 15
        
        # Order items
        line_spacing = font_size + 3
        checkbox_size = font_size - 2
        p.setFont("Helvetica", font_size)
        
        order_items = list(order.items.all())
        
        for item in order_items:
            # Check for page overflow (only happens at size 10 for large orders)
            if y < BOTTOM_MARGIN:
                # Draw page number before moving to next page
                _draw_page_number(p, current_page, total_pages, width)
                p.showPage()
                current_page += 1
                y = height - TOP_MARGIN
                
                # Continuation header
                p.setFont("Helvetica-Bold", font_size)
                p.drawString(50, y, f"Customer #{customer_number} (continued)")
                y -= font_size + 8
                p.line(50, y, width - 50, y)
                y -= 15
                p.setFont("Helvetica", font_size)
            
            product_name = item.product.name if item.product else 'Unknown Product'
            quantity = item.quantity
            
            # Checkbox (proportional size)
            p.rect(60, y - 3, checkbox_size, checkbox_size)
            p.drawString(60 + checkbox_size + 10, y, f"{product_name}")
            p.drawString(width - 100, y, f"Qty: {quantity}")
            y -= line_spacing
        
        # Draw page number
        _draw_page_number(p, current_page, total_pages, width)
        p.showPage()
    
    # Summary page with header
    current_page += 1
    y = height - TOP_MARGIN
    is_first_summary_page = True
    
    # Header section (only on first summary page)
    p.setFont("Helvetica-Bold", 18)
    p.drawString(50, y, "PACKING LIST")
    y -= 25
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, f"Program: {combined_order.program.name}")
    y -= 20
    p.drawString(50, y, f"Packer: {packer.name if packer else 'Unassigned'}")
    y -= 20
    p.drawString(50, y, f"Combined Order: {combined_order.name}")
    y -= 20
    
    p.setFont("Helvetica", 11)
    p.drawString(50, y, f"Generated: {combined_order.created_at.strftime('%Y-%m-%d %H:%M')}")
    y -= 15
    p.drawString(50, y, f"Total Orders: {len(orders)}")
    y -= 25
    
    # Separator line
    p.line(50, y, width - 50, y)
    y -= 20
    
    # Summary section
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "SUMMARY")
    y -= 25
    
    for category, products in summarized_data.items():
        # Check for page break
        if y < BOTTOM_MARGIN + 30:
            _draw_page_number(p, current_page, total_pages, width)
            p.showPage()
            current_page += 1
            y = height - TOP_MARGIN
            is_first_summary_page = False
            
            # Continuation header
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, "SUMMARY (continued)")
            y -= 25
        
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, f"{category}:")
        y -= 18
        
        p.setFont("Helvetica", 11)
        for product_name, qty in products.items():
            if y < BOTTOM_MARGIN + 30:
                _draw_page_number(p, current_page, total_pages, width)
                p.showPage()
                current_page += 1
                y = height - TOP_MARGIN
                
                p.setFont("Helvetica-Bold", 14)
                p.drawString(50, y, "SUMMARY (continued)")
                y -= 25
                p.setFont("Helvetica", 11)
            
            p.drawString(70, y, f"{product_name}: {qty}")
            y -= 15
        
        y -= 8
    
    # Packer signature line at bottom
    y -= 20
    p.setFont("Helvetica", 10)
    p.drawString(50, y, "Packed by: _______________________")
    p.drawString(300, y, "Date: _____________")
    
    # Final page number
    _draw_page_number(p, current_page, total_pages, width)
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer
