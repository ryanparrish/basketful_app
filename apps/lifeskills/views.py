# apps/lifeskills/views.py
"""Views for LifeSkills app, including participant dashboard."""
# Django core
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
# First party 
from apps.account.models import AccountBalance
from apps.voucher.models import Voucher
from apps.orders.models import Order
from apps.orders.utils.order_services import encode_order_id
from core.utils import can_place_order


def get_active_vouchers(participant):
    """
    Return active vouchers for a participant, or an empty queryset if none.
    """
    try:
        account_balance = AccountBalance.active_accounts.get(
            participant=participant
        )
    except ObjectDoesNotExist:
        return Voucher.active_vouchers.none()
    return Voucher.active_vouchers.filter(
        account=account_balance,
        state=Voucher.APPLIED
    )


@login_required
def participant_dashboard(request):
    """
    Participant dashboard with account info, orders, and vouchers.
    """
    try:
        participant = request.user.participant
    except ObjectDoesNotExist:
        messages.error(
            request, "No participant profile found for this account."
        )
        return redirect("index")  # or some other fallback page

    account = AccountBalance.objects.filter(participant=participant).first()
    orders = Order.objects.filter(
        account__participant=participant
    ).order_by("-created_at")
    program = participant.program if participant.program else None
    has_vouchers = get_active_vouchers(participant).exists()

    # Check order window
    can_order, order_window_context = can_place_order(participant)

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
            "can_order": can_order,
            "order_window": order_window_context,
        },
    )
