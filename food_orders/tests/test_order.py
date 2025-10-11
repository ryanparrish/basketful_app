# food_orders/tests/test_order_validation.py

"""
Comprehensive pytest-based test suite for validating order creation, voucher usage,
and hygiene balance logic in the food_orders app.

This module refactors the previous Django TestCase classes into pytest functions
with extremely verbose comments for clarity.
"""

# ----------------------
# Standard library
# ----------------------
import logging
from decimal import Decimal
from types import SimpleNamespace

# ----------------------
# Django imports
# ----------------------
from django.core.exceptions import ValidationError
from django.contrib.messages import get_messages
from django.urls import reverse

# ----------------------
# Third-party imports
# ----------------------
import pytest

# ----------------------
# Local app imports
# ----------------------
from food_orders.models import Order, OrderItem, OrderVoucher, Voucher
from food_orders.utils.order_validation import OrderValidation
from food_orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from test_helper import (
    create_category,
    create_product,
    create_participant,
    create_voucher,
    create_order,
    add_items_to_order,
    make_items,
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Optional: set the logging level (DEBUG, INFO, WARNING, ERROR)
logger.setLevel(logging.INFO)

# -----------------------------
# Order validation tests
# -----------------------------

@pytest.mark.django_db
def test_simple_order_creation_verbose():
    """
    Happy path:
    1. Create a category and product
    2. Create participant and voucher
    3. Create order and add items
    4. Validate order items
    5. Assert order and item quantities are correct
    """
    category = create_category("Canned Goods")
    product = create_product("Beans", Decimal("10"), category)

    participant = create_participant(email="simple@example.com")
    voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

    order = create_order(participant)
    items = make_items([(product, 3)])
    add_items_to_order(order, items)

    utils = OrderValidation()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert Order.objects.count() == 1
    assert OrderItem.objects.count() == 1
    assert order.items.first().quantity == 3

# ============================================================
# Order and OrderItem Model Tests
# ============================================================
"""
These tests verify the calculated properties on the Order and OrderItem models.
"""

@pytest.mark.django_db
def test_order_item_total_price(order_with_items_setup):
    """Checks that the `total_price()` method on an OrderItem works correctly."""
    # --- ARRANGE ---
    item1 = order_with_items_setup["item1"] # 3 * $2.50
    item2 = order_with_items_setup["item2"] # 2 * $3.00

    # --- ASSERT ---
    assert item1.total_price() == Decimal("7.50")
    assert item2.total_price() == Decimal("6.00")

@pytest.mark.django_db
def test_order_total_price(order_with_items_setup):
    """Checks that the `total_price` property on an Order correctly sums its items."""
    # --- ARRANGE ---
    order = order_with_items_setup["order"] # $7.50 + $6.00

    # --- ASSERT ---
    assert order.total_price == Decimal("13.50")

@pytest.mark.django_db
def test_order_with_multiple_products_verbose():
    """
    Happy path with multiple products in different categories.
    Ensures order items and categories interact correctly.
    """
    cat1 = create_category("Canned Goods")
    cat2 = create_category("Hygiene")

    p1 = create_product("Beans", Decimal("5"), cat1)
    p2 = create_product("Soap", Decimal("15"), cat2)

    participant = create_participant(email="multi@example.com")
    create_voucher(participant, multiplier=2, base_balance=Decimal("50"))

    order = create_order(participant)
    items = make_items([(p1, 2), (p2, 1)])
    add_items_to_order(order, items)

    utils = OrderValidation()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert order.items.count() == 2
    assert order.items.first().product.name == "Beans"
    assert order.items.last().product.name == "Soap"

@pytest.mark.django_db
def test_order_with_mixed_categories_under_balances():
    """
    Test order with both hygiene and regular items within balance limits.
    Ensures mixed category logic works.
    """
    cat_canned = create_category("Canned Goods")
    cat_hygiene = create_category("Hygiene")

    p1 = create_product("Beans", Decimal("20"), cat_canned)
    p2 = create_product("Soap", Decimal("30"), cat_hygiene)

    participant = create_participant(email="mixed@example.com")
    participant.accountbalance.base_balance = Decimal("150")
    participant.accountbalance.save()

    voucher = create_voucher(participant, multiplier=1, base_balance=Decimal("150"))

    order = create_order(participant)
    items = make_items([(p1, 2), (p2, 1)])
    add_items_to_order(order, items)

    utils = OrderValidation()
    utils.validate_order_items(items, participant, participant.accountbalance)

    # Assertions
    assert order.items.count() == 2
    assert voucher.voucher_amnt == Decimal("150")



@pytest.mark.django_db
def test_products_without_categories_verbose():
    """
    Test products without a category are skipped gracefully.
    Uses in-memory mock product object.
    """
    product_no_cat = SimpleNamespace(name="Uncategorized Product", price=Decimal("10"), category=None)

    participant = create_participant(name="No Category User")
    create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

    items = [type("OrderItemData", (), {"product": product_no_cat, "quantity": 1})]

    utils = OrderValidation()
    # Should not raise any exception
    utils.validate_order_items(items, participant, participant.accountbalance)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@pytest.mark.django_db
def test_submit_order_view(client):
    """End-to-end test for submitting an order with vouchers applied."""
    VoucherSettingFactory.create()

    # --- Setup user, participant, and account ---
    user = UserFactory(username="testuser", password="password123")
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    account.save()  # ensure enough for order
    
    logger.info("FoodOrdersConfig.ready() called — importing signals...")
    import food_orders.signals
    logger.info(" food_orders.signals successfully imported")

    # --- Category & Products ---
    grocery_category = CategoryFactory(name="Grocery")
    product1 = ProductFactory(name="Apple", price=Decimal("10"), category=grocery_category)
    product2 = ProductFactory(name="Banana", price=Decimal("20"), category=grocery_category)

    vouchers = account.vouchers.all()
    voucher_count = vouchers.count()
    logger.debug(f"Participant {participant.id} has {voucher_count} vouchers.")

    for voucher in vouchers:
        logger.debug(f"Voucher {voucher.id} — active: {voucher.active}, state: {voucher.state}")
    logger.debug(f"Participant {participant.id} base balance: {account.base_balance}")

    # --- Sanity check for vouchers and balances ---
    applied_vouchers = Voucher.objects.filter(account=account, state="applied")
    total_applied = sum(v.voucher_amnt for v in applied_vouchers)
    logger.debug("Initial total applied vouchers: %s", total_applied)
    logger.debug("Account available balance: %s", account.available_balance)

    # --- Login ---
    client.force_login(user)

    # --- Session cart setup ---
    session = client.session
    session["cart"] = {
        str(product1.id): 2,  # 2 * 10 = 20
        str(product2.id): 1,  # 1 * 20 = 20
    }
    session.save()
    logger.debug("Cart session: %s", session["cart"])

    # --- Define form payload ---
    payload = {"confirm": True}

    # --- POST to submit order ---
    url = reverse("submit_order")
    response = client.post(url, data=payload, follow=True)

    # --- Logging POST response ---
    logger.info("POST submit_order status: %s", response.status_code)
    logger.info("Redirect chain: %s", response.redirect_chain)
    logger.info("Templates used: %s", [t.name for t in response.templates])
    logger.info("Response content snippet: %s", response.content.decode()[:200])

    # Capture messages from POST
    messages_list = list(get_messages(response.wsgi_request))
    for m in messages_list:
        logger.warning("Validation/message: %s", m)

    # --- Assert response ---
    assert response.status_code == 200
    templates_rendered = [t.name for t in response.templates]

    if "food_orders/order_success.html" in templates_rendered:
        logger.info("Order success page rendered")
        content = response.content.decode()
        # Use a more flexible check for success
        assert "Thank you" in content and "order" in content, (
        "Order success message not found in page content"
        )
    elif "food_orders/participant_dashboard.html" in templates_rendered:
        logger.info("Redirected to participant dashboard after order")
    else:
        pytest.fail(f"Unexpected template rendered: {templates_rendered}")

    # --- Verify order created ---
    order = Order.objects.first()
    assert order is not None, "Order should be created"
    assert order.total_price == Decimal("40"), f"Expected order total 40, got {order.total_price}"
    logger.info("Order Total Price is %s", order.total_price)

    # --- Verify cart cleared ---
    session = client.session
    assert session.get("cart") == {}, "Cart should be empty after submission"

    # --- Verify account balance used ---
    account.refresh_from_db()
    assert account.available_balance == Decimal("0"), (
        f"Expected available_balance to be 0.00 after purchase, available_balance = {account.available_balance}"
    )

    applied_vouchers = Voucher.objects.filter(ordervoucher__order=order, active=True, state='applied')

    # Sum up their amounts (assuming you have a `voucher_amount` field or method)
    total_applied = sum(v.voucher_amount for v in applied_vouchers)

    # Assert against the expected total
    expected_total = Decimal("0")  # adjust as needed
    assert total_applied == expected_total, f"Expected total {expected_total}, got {total_applied}"

    logger.info("Total vouchers applied: %s", total_applied)
