import random
from django.contrib.auth import get_user_model
import json
from django.shortcuts import get_object_or_404
from .models import Product, Order

User = get_user_model()


def get_product_prices_json():
    """Return product prices as JSON for inline admin scripts."""
    products = Product.objects.all().values('id', 'price')
    return json.dumps({str(p['id']): float(p['price']) for p in products})

def get_order_or_404(order_id):
    """Return Order object or 404."""
    return get_object_or_404(Order, pk=order_id)

def get_order_print_context(order):
    """
    Return context dict for rendering the print page.
    Assumes Participant is only accessible through AccountBalance reverse relationship.
    """
    # Access participant through account → accountbalance → participant
    # Adjust the related_name if yours is different
    account_balance = getattr(order, 'account', None)
    participant = None

    if account_balance:
        # Assuming AccountBalance has a OneToOneField or ForeignKey to Participant
        # If multiple balances per account, pick the first
        balance_qs = getattr(account_balance, 'accountbalance_set', None)
        if balance_qs:
            first_balance = balance_qs.first()
            if first_balance:
                participant = getattr(first_balance, 'participant', None)

    return {
        "order": order,
        "items": order.items.select_related("product").all(),
        "total": order.total_price(),
        "customer": participant,
        "created_at": order.created_at,
    }

def generate_unique_username(full_name):
    base_username = full_name.lower().replace(" ", "_")
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1
    return username

def generate_memorable_password():
    adjectives = ['sunny', 'brave', 'gentle', 'fuzzy', 'bright']
    nouns = ['apple', 'river', 'tiger', 'sky', 'love', 'forest']
    return f"{random.choice(adjectives)}-{random.choice(nouns)}-{random.randint(100, 999)}"

def set_random_password_for_user(user):
    """
    Sets a memorable random password for the given unsaved User object.
    Returns the generated password.
    """
    password = generate_memorable_password()
    user.set_password(password)
    user.must_change_password = True
    return password
def generate_username_if_missing(user):
    if not user.username:
        full_name = f"{user.first_name} {user.last_name}".strip()
        user.username = generate_unique_username(full_name)
