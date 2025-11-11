#views.py
# Standard library
import json
import logging

# Django core
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

# Django auth
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView

# Local app
from .models import AccountBalance, Order, Product, Participant, Voucher
from .forms import ParticipantUpdateForm, CustomLoginForm
from .utils.order_utils import OrderItemData, OrderOrchestration
from .utils.utils import decode_order_hash, encode_order_id

logger = logging.getLogger(__name__)

class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change that resets the must_change_password flag."""
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        return response


def get_active_vouchers(participant):
    """Return active vouchers for a participant, or an empty queryset if none."""
    try:
        account_balance = AccountBalance.objects.get(participant=participant)
    except AccountBalance.DoesNotExist:
        return Voucher.objects.none()
    return Voucher.objects.filter(account=account_balance, active=True)


def index(request):
    return render(request, "food_orders/index.html")

def custom_login_view(request):
    """Login view with captcha enabled after 3 failed attempts."""
    show_captcha = request.session.get("login_failures", 0) >= 3

    if request.method == "POST":
        form = CustomLoginForm(
            data=request.POST, request=request, use_captcha=show_captcha
        )
        if form.is_valid():
            login(request, form.get_user())
            request.session["login_failures"] = 0
            return redirect("participant_dashboard")
        else:
            request.session["login_failures"] = request.session.get(
                "login_failures", 0
            ) + 1
    else:
        form = CustomLoginForm(use_captcha=show_captcha)

    return render(
        request,
        "registration/login.html",
        {"form": form, "show_captcha": show_captcha},
    )


@login_required
def order_detail(request, order_hash):
    """
    Show details for a single order using a hashid.
    Allows duplication into a new cart.
    """
    participant = request.user.participant

    # Decode hashid to get the real order ID
    order_id = decode_order_hash(order_hash)
    if order_id is None:
        # Invalid hashid → 404
        return get_object_or_404(Order, pk=-1)

    # Fetch the order only if it belongs to this participant
    order = get_object_or_404(Order, id=order_id, account__participant=participant)

    if request.method == "POST" and "duplicate_order" in request.POST:
        cart = {str(item.product.id): item.quantity for item in order.items.all()}
        request.session["cart"] = cart
        request.session.modified = True
        return redirect("review_order")

    return render(
        request,
        "food_orders/order_detail.html",
        {"order": order, "order_items": order.items.all()},
    )


@login_required
def participant_dashboard(request):
    """Participant dashboard with account info, orders, and vouchers."""
    try:
        participant = request.user.participant
    except ObjectDoesNotExist:
        messages.error(request, "No participant profile found for this account.")
        return redirect("index")  # or some other fallback page

    account = AccountBalance.objects.filter(participant=participant).first()
    orders = Order.objects.filter(account__participant=participant).order_by("-created_at")
    program = participant.program if participant.program else None
    has_vouchers = get_active_vouchers(participant).exists()

    for order in orders:
        order.hash = encode_order_id(order.id)

    return render(
        request,
        "food_orders/participant_dashboard.html",
        {
            "account": account,
            "orders": orders,
            "participant": participant,
            "program": program,
            "has_vouchers": has_vouchers,
        },
    )

@login_required
def product_view(request):
    """Product selection page for creating a new order."""
    query = request.GET.get("q", "")
    products = Product.objects.all().order_by("category", "name")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    participant = request.user.participant
    if not get_active_vouchers(participant).exists():
        return redirect("participant_dashboard")

    # Group products by category
    products_by_category = {}
    all_products = {}

    for product in products:
        products_by_category.setdefault(product.category, []).append(product)
        all_products[product.id] = {"name": product.name, "price": float(product.price)}

    products_json = mark_safe(json.dumps(all_products))

    return render(
        request,
        "food_orders/create_order.html",
        {
            "products_by_category": products_by_category,
            "products_json": products_json,
            "query": query,
        },
    )


@require_POST
@login_required
def update_cart(request):
    """Update the session cart via AJAX."""
    try:
        cart = json.loads(request.body)
        request.session["cart"] = cart
        request.session.modified = True
        return JsonResponse({"status": "ok"})
    except json.JSONDecodeError:
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON"}, status=400
        )


@login_required
def account_update_view(request):
    """Update participant info or password."""
    participant = Participant.objects.get(user=request.user)

    if request.method == "POST":
        user_form = ParticipantUpdateForm(request.POST, instance=participant)
        password_form = PasswordChangeForm(request.user, request.POST)

        if "update_info" in request.POST and user_form.is_valid():
            user_form.save()
            request.user.first_name = request.POST.get("first_name", "")
            request.user.last_name = request.POST.get("last_name", "")
            request.user.save()
            messages.success(request, "Your account info was updated.")
            return redirect("account_update")

        elif "change_password" in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was updated.")
            return redirect("account_update")
    else:
        user_form = ParticipantUpdateForm(instance=participant)
        password_form = PasswordChangeForm(request.user)

    return render(
        request,
        "food_orders/account_update.html",
        {"user_form": user_form, "password_form": password_form},
    )


@login_required
@transaction.atomic
def review_order(request):
    """Review or validate the current cart before submitting."""
    cart = request.session.get("cart", {})
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

        order_utils = OrderOrchestration()
        try:
            # Run validation-only mode
            order_utils.create_order(account, order_items_data=order_items, validate_only=True)
            # If successful, redirect to final submission
            return redirect("submit_order")

        except ValidationError as e:
            messages.error(request, str(e))

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
        order.confirm()
        logger.debug("=== ORDER DEBUG START ===")
        logger.debug("Order type: %s", type(order))
        logger.debug("Order module: %s", getattr(order.__class__, "__module__", None))
        logger.debug("Has use_voucher: %s", hasattr(order, "use_voucher"))
        logger.debug("Dir(order): %s", dir(order))
        logger.debug("Order repr: %s", repr(order))
        logger.debug("=== ORDER DEBUG END ===")

        order.use_voucher()

    except ValidationError as e:
        messages.error(request, str(e))
        return redirect("review_order")
    
 # Clear cart
    request.session["cart"] = {}
    request.session["last_order_id"] = order.id
    request.session.modified = True

    # Redirect to success page
    return redirect("order_success")

@login_required
def order_success(request):
    # Pop the order ID from the session
    order_id = request.session.pop("last_order_id", None)
    if not order_id:
        messages.warning(request, "No recent order to display.")
        return redirect("participant_dashboard")  # fallback page

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
    order = get_object_or_404(
        Order, pk=order_id, account__participant=request.user.participant
    )

    try:
        new_order = order.edit()
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("order_history")

    request.session["cart"] = {
        str(item.product_id): item.quantity for item in new_order.items.all()
    }
    request.session.modified = True

    return redirect("review_order")
