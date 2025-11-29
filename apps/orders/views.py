# orders/views.py
"""Views for managing food orders."""
# Standard library
import logging
# Django core
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError
# First-party
from apps.account.models import AccountBalance
from apps.pantry.models import Product
# Local application
from .models import Order, OrderItemData
from .utils.order_utils import OrderOrchestration
from .utils.order_services import decode_order_hash


logger = logging.getLogger(__name__)


@login_required
@transaction.atomic
def review_order(request):
    """Review or validate the current cart before submitting."""
    cart = request.session.get("cart", {})
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("create_order")

    products = Product.objects.filter(id__in=cart.keys())
    cart_items = []
    total = 0

    for product in products:
        qty = cart.get(str(product.id), 0)
        subtotal = product.price * qty
        total += subtotal
        cart_items.append({"product": product, "quantity": qty, "subtotal": subtotal})

    if request.method == "POST":
        participant = request.user.participant
        account = AccountBalance.objects.select_for_update().get(participant=participant)

        products_map = {p.id: p for p in products}
        order_items = [
            OrderItemData(product=products_map[int(pid)], quantity=qty)
            for pid, qty in cart.items()
            if products_map.get(int(pid))
        ]

        # Validate without creating the order
        try:
            order = Order(account=account)
            # Temporarily attach items for validation
            order.items_set = order_items  # or use your OrderOrchestration method
            order.full_clean()  # triggers hygiene, category, voucher validation
            return redirect("submit_order")
        except ValidationError as e:
            messages.error(request, e)
    
    return render(
        request,
        "food_orders/review_order.html",
        {"cart_items": cart_items, "total": total},
    )


@login_required
@transaction.atomic
def submit_order(request):
    """Submit the current cart as a new order."""
    cart = request.session.get("cart", {})
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect("create_order")

    participant = request.user.participant
    account = AccountBalance.objects.select_for_update().get(participant=participant)

    products = Product.objects.in_bulk([int(pid) for pid in cart.keys()])
    order_items = [
        OrderItemData(product=products[int(pid)], quantity=qty)
        for pid, qty in cart.items()
        if products.get(int(pid))
    ]

    order_utils = OrderOrchestration()

    try:
        order = order_utils.create_order(account, order_items_data=order_items)
        order.confirm()  # calls clean() internally, runs all validation

    except ValidationError as e:
        messages.error(request, e)
        return redirect("review_order")

    # Clear cart and store last order
    request.session["cart"] = {}
    request.session["last_order_id"] = order.id
    request.session.modified = True

    return redirect("order_success")


@login_required
def order_success(request):
    """Display order success page for the last submitted order."""
    order_id = request.session.pop("last_order_id", None)
    if not order_id:
        messages.warning(request, "No recent order to display.")
        return redirect("participant_dashboard")

    try:
        order = Order.objects.get(id=order_id, account__participant=request.user.participant)
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect("participant_dashboard")

    order.success_viewed = True
    order.save(update_fields=["success_viewed"])

    return render(request, "food_orders/order_success.html", {"order": order})


@login_required
@transaction.atomic
def edit_order(request, order_id):
    """Clone an existing order into a new editable draft."""
    order = get_object_or_404(Order, pk=order_id, account__participant=request.user.participant)

    try:
        new_order = order.edit()
    except ValueError as e:
        messages.error(request, e)
        return redirect("order_history")

    request.session["cart"] = {
        str(item.product_id): item.quantity for item in new_order.items.all()
    }
    request.session.modified = True
    return redirect("review_order")


@login_required
def order_detail(request, order_hash):
    """Show details for a single order using a hashid."""
    participant = request.user.participant
    order_id = decode_order_hash(order_hash)
    if order_id is None:
        return get_object_or_404(Order, pk=-1)  # force 404

    order = get_object_or_404(Order, id=order_id, account__participant=participant)

    if request.method == "POST" and "duplicate_order" in request.POST:
        request.session["cart"] = {str(item.product.id): item.quantity for item in order.items.all()}
        request.session.modified = True
        return redirect("review_order")

    return render(request, "food_orders/order_detail.html", {"order": order, "order_items": order.items.all()})
