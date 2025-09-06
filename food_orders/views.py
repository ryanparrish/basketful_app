# Django core
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse_lazy
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

# Django auth
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordChangeView

# Local app
from .models import AccountBalance, Order, Product, Participant, Voucher
from .forms import ParticipantUpdateForm, CustomLoginForm

# Standard library
import json

class CustomPasswordChangeView(PasswordChangeView):
    success_url = reverse_lazy('home')  # or wherever you want

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        return response

def get_active_vouchers(participant):
    try:
        account_balance = AccountBalance.objects.get(participant=participant)
    except AccountBalance.DoesNotExist:
        return Voucher.objects.none()  # No vouchers if no AccountBalance found

    return Voucher.objects.filter(account=account_balance, active=True)

def index(request):
     return render(request, 'food_orders/index.html')
       
def custom_login_view(request):
    show_captcha = request.session.get('login_failures', 0) >= 3

    if request.method == 'POST':
        form = CustomLoginForm(data=request.POST, request=request, use_captcha=show_captcha)
        if form.is_valid():
            login(request, form.get_user())
            request.session['login_failures'] = 0  # reset
            return redirect('participant_dashboard')
        else:
            request.session['login_failures'] = request.session.get('login_failures', 0) + 1
    else:
        form = CustomLoginForm(use_captcha=show_captcha)

    return render(request, 'registration/login.html', {'form': form, 'show_captcha': show_captcha})

@login_required
def order_detail(request, order_id):
    participant = request.user.participant
    order = get_object_or_404(Order, id=order_id, account__participant=participant)
    
    if request.method == "POST" and 'duplicate_order' in request.POST:
        # Create a new cart session from this order
        cart = {}
        for item in order.items.all():
            cart[str(item.product.id)] = item.quantity

        request.session['cart'] = cart
        request.session.modified = True

        return redirect('review_order')

    order_items = order.items.all()

    return render(request, 'food_orders/order_detail.html', {
        'order': order,
        'order_items': order_items,
    })

@login_required
def participant_dashboard(request):
    participant = request.user.participant
    account = AccountBalance.objects.filter(participant=participant).first()
    orders = Order.objects.filter(account__participant=participant).order_by('-created_at')
    program = participant.program  # via FK
    has_vouchers = get_active_vouchers(participant).exists()

    return render(request, 'food_orders/participant_dashboard.html', {
        'account': account,
        'orders': orders,
        'participant': participant,
        'program': program,
        'has_vouchers': has_vouchers,
    })

@login_required
def create_order(request):
    # Get search term from query params
    query = request.GET.get("q", "")

    # Filter products if search term exists
    products = Product.objects.all().order_by('category', 'name')
    if query:
        products = products.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(category__name__icontains=query)  # if category has a 'name' field
        )

    participant = request.user.participant
    has_vouchers = get_active_vouchers(participant).exists()

    if not has_vouchers:
        print("Redirecting to dashboard - no vouchers are active")
        return redirect('participant_dashboard')

    # Group products by category
    products_by_category = {}
    all_products = {}

    for product in products:
        products_by_category.setdefault(product.category, []).append(product)
        all_products[product.id] = {
            'name': product.name,
            'price': float(product.price),
        }

    products_json = mark_safe(json.dumps(all_products))

    return render(request, 'food_orders/create_order.html', {
        'products_by_category': products_by_category,
        'products_json': products_json,
        'query': query,  # pass current search back to template
    })

@require_POST
@login_required
def update_cart(request):
    try:
        cart = json.loads(request.body)
        request.session['cart'] = cart
        request.session.modified = True
        return JsonResponse({'status': 'ok'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

@login_required
def account_update_view(request):
    participant = Participant.objects.get(user=request.user)

    if request.method == 'POST':
        user_form = ParticipantUpdateForm(request.POST, instance=participant)
        password_form = PasswordChangeForm(request.user, request.POST)

        if 'update_info' in request.POST and user_form.is_valid():
            user_form.save()
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.save()
            messages.success(request, 'Your account info was updated.')
            return redirect('account_update')

        elif 'change_password' in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was updated.')
            return redirect('account_update')
    else:
        user_form = ParticipantUpdateForm(instance=participant)
        password_form = PasswordChangeForm(request.user)

    return render(request, 'food_orders/account_update.html', {
        'user_form': user_form,
        'password_form': password_form,
    })

@login_required
def review_order(request):
    cart = request.session.get('cart', {})
    product_ids = cart.keys()
    products = Product.objects.filter(id__in=product_ids)

    cart_items = []
    total = 0

    for product in products:
        qty = cart.get(str(product.id), 0)
        subtotal = product.price * qty
        total += subtotal
        cart_items.append({
            'product': product,
            'quantity': qty,
            'subtotal': subtotal,
        })

    return render(request, 'food_orders/review_order.html', {
        'cart_items': cart_items,
        'total': total
    })

@login_required
@transaction.atomic
def submit_order(request):
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('create_order')

    participant = request.user.participant
    account = AccountBalance.objects.select_for_update().get(participant=participant)

    product_ids = [int(pid) for pid in cart.keys()]
    products = Product.objects.in_bulk(product_ids)

    order_items = [
        OrderItemData(product=products[int(pid)], quantity=qty)
        for pid, qty in cart.items()
        if products.get(int(pid))
    ]

    # Create, validate, and confirm order in one call
    try:
        order = create_order(account, order_items)
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('review_order')

    # Clear session cart
    request.session['cart'] = {}
    request.session.modified = True

    return render(request, 'food_orders/order_success.html', {'order': order})


@login_required
@transaction.atomic
def edit_order(request, order_id):
    # Fetch the order for the current participant
    order = get_object_or_404(Order, pk=order_id, account__participant=request.user.participant)

    try:
        # Call the model wrapper method (delegates to OrderUtils)
        new_order = order.edit()
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('order_history')  # Redirect if order cannot be edited

    # Pre-fill the session cart with the cloned order items
    request.session['cart'] = {item.product_id: item.quantity for item in new_order.items.all()}
    request.session.modified = True

    return redirect('food_orders/review_order.html')  # or wherever your order edit form is


