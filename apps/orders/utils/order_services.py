# orders/utils/order_services.py
"""Utility services for Order processing."""
# Standard library imports  
import logging
from io import BytesIO
from hashids import Hashids
# Django imports
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# --- Configuration ---
SALT = getattr(settings, "HASHIDS_SALT")
MIN_LENGTH = getattr(settings, "HASHIDS_MIN_LENGTH", 10)

if not SALT:
    raise ValueError("HASHIDS_SALT not configured in settings or environment")

# Initialize Hashids once
hashids = Hashids(salt=SALT, min_length=MIN_LENGTH)

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


def generate_packing_list_pdf(packing_list) -> BytesIO:
    """
    Generate a PDF packing list for a specific packer.
    
    Uses customer numbers only for privacy (no participant names).
    Shows orders assigned to this packer with their items.
    
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
    orders = packing_list.orders.all().select_related(
        'account__participant'
    ).prefetch_related('items__product')
    
    # Header
    y = height - 50
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
    y -= 10
    p.drawString(50, y, f"Total Orders: {orders.count()}")
    y -= 30
    
    # Separator line
    p.line(50, y, width - 50, y)
    y -= 20
    
    # Orders section
    for order in orders:
        # Check for page break
        if y < 120:
            p.showPage()
            y = height - 50
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y, f"PACKING LIST (continued) - Packer: {packer.name if packer else 'Unassigned'}")
            y -= 30
        
        # Order header with customer number only (privacy)
        p.setFont("Helvetica-Bold", 12)
        # Access participant through account
        participant = order.account.participant if order.account else None
        customer_number = getattr(participant, 'customer_number', 'N/A') if participant else 'N/A'
        p.drawString(50, y, f"Customer #{customer_number}")
        y -= 15
        
        # Order items
        p.setFont("Helvetica", 10)
        order_items = order.items.all()
        
        for item in order_items:
            if y < 80:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica-Bold", 12)
                p.drawString(50, y, f"PACKING LIST (continued) - Packer: {packer.name if packer else 'Unassigned'}")
                y -= 30
                p.setFont("Helvetica", 10)
            
            product_name = item.product.name if item.product else 'Unknown Product'
            quantity = item.quantity
            # Checkbox for packer to mark
            p.rect(60, y - 3, 10, 10)  # Empty checkbox
            p.drawString(80, y, f"{product_name}")
            p.drawString(width - 100, y, f"Qty: {quantity}")
            y -= 15
        
        # Spacing between orders
        y -= 10
        p.line(50, y, width - 50, y)
        y -= 15
    
    # Footer with summary
    if y < 100:
        p.showPage()
        y = height - 50
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "SUMMARY")
    y -= 20
    
    # Calculate totals from packing list summarized data
    summarized_data = packing_list.summarized_data or {}
    p.setFont("Helvetica", 10)
    
    for category, products in summarized_data.items():
        if y < 60:
            p.showPage()
            y = height - 50
        
        p.setFont("Helvetica-Bold", 11)
        p.drawString(50, y, f"{category}:")
        y -= 15
        
        p.setFont("Helvetica", 10)
        for product_name, qty in products.items():
            if y < 60:
                p.showPage()
                y = height - 50
            p.drawString(70, y, f"{product_name}: {qty}")
            y -= 12
        
        y -= 5
    
    # Packer signature line at bottom
    y -= 20
    p.setFont("Helvetica", 10)
    p.drawString(50, y, "Packed by: _______________________")
    p.drawString(300, y, "Date: _____________")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer
