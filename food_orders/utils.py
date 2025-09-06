# utils.py
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

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
