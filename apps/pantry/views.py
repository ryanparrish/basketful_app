"""Views for food ordering application."""
# views.py
# Standard library
import json
import logging

# Django core
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

# Django auth
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
# First-party
from apps.account.models import Participant
from apps.account.forms import ParticipantUpdateForm
# Local application
from .models import Product
from .utils import get_active_vouchers

logger = logging.getLogger(__name__)



@login_required
def product_view(request):
    """Product selection page for creating a new order."""
    query = request.GET.get("q", "")
    
    # Debug: Check total products
    total_products = Product.objects.count()
    logger.info(f"Total products in database: {total_products}")
    
    products = Product.objects.filter(
        category__isnull=False,
        active=True
    ).select_related('category').order_by("category", "name")
    
    logger.info(f"Products with categories: {products.count()}")
    logger.info(f"SQL Query: {products.query}")
    logger.info(f"Query parameter: '{query}'")

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )
        logger.info(f"Products after query filter: {products.count()}")

    participant = request.user.participant
    active_vouchers = get_active_vouchers(participant)
    logger.info(f"Active vouchers for {participant}: {active_vouchers.count()}")
    
    logger.info(f"Products before voucher check: {products.count()}")
    
    if not active_vouchers.exists():
        messages.warning(
            request,
            "You don't have any active vouchers. Please contact your coach."
        )
        return redirect("participant_dashboard")
    
    logger.info(f"Products after voucher check: {products.count()}")

    # Group products by category
    products_by_category = {}
    all_products = {}
    
    # Force evaluation of queryset to a list
    logger.info(f"About to convert to list, products count: {products.count()}")
    # Create a fresh queryset to avoid any caching issues
    products_fresh = Product.objects.filter(
        category__isnull=False,
        active=True
    ).select_related('category').order_by("category", "name")
    products_list = list(products_fresh)
    logger.info(f"Starting to process {len(products_list)} products")
    
    for idx, product in enumerate(products_list):
        logger.info(
            f"Processing product {idx + 1}: ID={product.id}, "
            f"Name={product.name}, Category ID={product.category_id}"
        )
        category = product.category
        products_by_category.setdefault(category, []).append(product)
        all_products[product.id] = {
            "name": product.name,
            "price": float(product.price)
        }
        if idx == 0:
            logger.info(f"First product processed successfully: {product.name}")

    logger.info(f"Total products to display: {len(all_products)}")
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
        "account/account_update.html",
        {"user_form": user_form, "password_form": password_form},
    )

