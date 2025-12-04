"""Views for food ordering application."""
# views.py
# Standard library
import json
import logging

# Django core
from django.contrib import messages
from django.contrib.postgres.search import TrigramSimilarity
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


def get_base_products():
    """Get base queryset of active products with categories."""
    return Product.objects.filter(
        category__isnull=False,
        active=True
    ).select_related('category').order_by("category", "name")


def search_products(queryset, query):
    """
    Search products using fuzzy matching with trigram similarity.
    Falls back to basic contains search if trigrams aren't available.
    """
    if not query:
        return queryset
    
    try:
        # Use trigram similarity for fuzzy search
        queryset = queryset.annotate(
            name_similarity=TrigramSimilarity('name', query),
            desc_similarity=TrigramSimilarity('description', query),
            cat_similarity=TrigramSimilarity('category__name', query),
        ).filter(
            Q(name_similarity__gt=0.1) |
            Q(desc_similarity__gt=0.1) |
            Q(cat_similarity__gt=0.1)
        ).order_by('-name_similarity', '-desc_similarity', '-cat_similarity')
    except Exception as e:
        logger.warning(
            f"Trigram search failed, using basic search: {e}"
        )
        # Fallback to basic case-insensitive search
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    return queryset


def group_products_by_category(products):
    """
    Group products by category and prepare JSON data.
    Returns tuple of (products_by_category, products_json).
    """
    products_by_category = {}
    all_products = {}
    
    for product in products:
        category = product.category
        products_by_category.setdefault(category, []).append(product)
        all_products[product.id] = {
            "name": product.name,
            "price": float(product.price)
        }
    
    products_json = mark_safe(json.dumps(all_products))
    return products_by_category, products_json


@login_required
def product_view(request):
    """Product selection page for creating a new order."""
    query = request.GET.get("q", "")
    
    # Get base products
    products = get_base_products()
    logger.info(f"Base products count: {products.count()}")
    
    # Apply search if query exists
    if query:
        products = search_products(products, query)
        logger.info(f"Products after search '{query}': {products.count()}")
    
    # Check for active vouchers
    participant = request.user.participant
    active_vouchers = get_active_vouchers(participant)
    
    if not active_vouchers.exists():
        messages.warning(
            request,
            "You don't have any active vouchers. "
            "Please contact your coach."
        )
        return redirect("participant_dashboard")
    
    # Group products and prepare data
    products_by_category, products_json = group_products_by_category(
        products
    )
    
    # Get existing cart from session for persistence
    session_cart = request.session.get("cart", {})
    
    logger.info(f"Total products to display: {len(products_by_category)}")

    return render(
        request,
        "pantry/create_order.html",
        {
            "products_by_category": products_by_category,
            "products_json": products_json,
            "query": query,
            "session_cart": json.dumps(session_cart),
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

