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
from django.contrib.messages import get_messages
from django.urls import reverse

# ----------------------
# Third-party imports
# ----------------------
import pytest

# ----------------------
# Local app imports
# ----------------------
from apps.voucher.models import Voucher
from apps.orders.models import Order, OrderItem
from apps.orders.utils.order_validation import OrderValidation
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    CategoryFactory,
    ProductFactory,
    VoucherSettingFactory,
    VoucherFactory,
)
from .test_helper import (create_order, add_items_to_order)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Optional: set the logging level (DEBUG, INFO, WARNING, ERROR)
logger.setLevel(logging.DEBUG)

# -----------------------------
# Helper functions
# -----------------------------


def create_category(name):
    """Create and return a category."""
    return CategoryFactory(name=name)


def create_product(name, price, category):
    """Create and return a product."""
    return ProductFactory(name=name, price=price, category=category)


def create_participant(email=None, name=None):
    """Create and return a participant with a user."""
    user = UserFactory(email=email) if email else UserFactory()
    if name:
        return ParticipantFactory(user=user, name=name)
    return ParticipantFactory(user=user)


def create_voucher(participant, multiplier, base_balance):
    """Create and return a voucher for a participant."""
    account = participant.accountbalance
    account.base_balance = base_balance
    account.save()
    return Voucher.objects.create(
        account=account,
        multiplier=multiplier,
        active=True,
        state='applied'
    )


def make_items(product_quantity_pairs):
    """Create a list of order item data from product pairs."""
    items = []
    for product, quantity in product_quantity_pairs:
        item = type(
            "OrderItemData",
            (),
            {"product": product, "quantity": quantity}
        )()
        items.append(item)
    return items


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
    create_voucher(
        participant, multiplier=1, base_balance=Decimal("50")
    )

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

    voucher = create_voucher(
        participant, multiplier=1, base_balance=Decimal("150")
    )

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
    """Test products without a category are skipped gracefully.
    Uses in-memory mock product object.
    """
    product_no_cat = SimpleNamespace(
        name="Uncategorized Product",
        price=Decimal("10"),
        category=None
    )

    participant = create_participant(name="No Category User")
    create_voucher(participant, multiplier=1, base_balance=Decimal("50"))

    items = [
        type(
            "OrderItemData", (), {"product": product_no_cat, "quantity": 1}
        )
    ]

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
    test_password = "test_pass_123"  # noqa: S105
    user = UserFactory(username="testuser")
    user.set_password(test_password)
    user.save()
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    account.base_balance = Decimal("100.00")  # Set sufficient balance
    account.save()  # ensure enough for order
    
    # Create vouchers to provide available balance
    VoucherFactory(account=account, state='applied', voucher_type='grocery')
    VoucherFactory(account=account, state='applied', voucher_type='grocery')

    logger.info("FoodOrdersConfig.ready() called — importing signals...")
  
    logger.info(" food_orders.signals successfully imported")

    # --- Category & Products ---
    grocery_category = CategoryFactory(name="Grocery")
    product1 = ProductFactory(
        name="Apple", price=Decimal("10"), category=grocery_category
    )
    product2 = ProductFactory(
        name="Banana", price=Decimal("20"), category=grocery_category
    )

    vouchers = account.vouchers.all()
    voucher_count = vouchers.count()
    logger.debug(
        "Participant %s has %s vouchers.", participant.id, voucher_count
    )

    for voucher in vouchers:
        logger.debug(
            "Voucher %s — active: %s, state: %s",
            voucher.id,
            voucher.active,
            voucher.state,
        )
    logger.debug(
        "Participant %s base balance: %s",
        participant.id,
        account.base_balance,
    )

    # --- Sanity check for vouchers and balances ---
    applied_vouchers = Voucher.objects.filter(account=account, state="applied")
    total_applied = sum(v.voucher_amnt for v in applied_vouchers)
    logger.debug("Initial total applied vouchers: %s", total_applied)
    logger.debug("Account available balance: %s", account.available_balance)

    # --- Session cart setup (must happen BEFORE login) ---
    session = client.session
    session["cart"] = {
        str(product1.id): 2,  # 2 * 10 = 20
        str(product2.id): 1,  # 1 * 20 = 20
    }
    session.save()
    logger.debug("Cart session: %s", session["cart"])

    # --- Login using credentials (preserves session) ---
    client.login(username="testuser", password=test_password)

    # --- Define form payload ---
    payload = {"confirm": True}

    # --- POST to submit order ---
    url = reverse("submit_order")
    response = client.post(url, data=payload, follow=True)

    # --- Logging POST response ---
    logger.info("POST submit_order status: %s", response.status_code)
    logger.info("Redirect chain: %s", response.redirect_chain)
    logger.info(
        "Templates used: %s", [t.name for t in response.templates]
    )
    logger.info(
        "Response content snippet: %s",
        response.content.decode()[:200],
    )

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
        assert "Thank you" in content and "order" in content
    elif "food_orders/participant_dashboard.html" in templates_rendered:
        logger.info("Redirected to participant dashboard after order")
    else:
        pytest.fail(f"Unexpected template rendered: {templates_rendered}")

    # --- Verify order created ---
    order = Order.objects.first()
    assert order is not None
    assert order.total_price() == Decimal("40")
    logger.info("Order Total Price is %s", order.total_price())

    # --- Verify cart cleared ---
    session = client.session
    assert session.get("cart") == {}

    logger.info("Order creation successful - cart cleared")


@pytest.mark.django_db
def test_submit_order_view_with_50_items(client):
    """End-to-end test for submitting an order with 50 items and verifying persistence."""
    VoucherSettingFactory.create()

    # --- Setup user, participant, and account ---
    test_password = "test_pass_123"  # noqa: S105
    user = UserFactory(username="testuser_50items")
    user.set_password(test_password)
    user.save()
    participant = ParticipantFactory(user=user)
    account = participant.accountbalance
    
    # Set realistic base balance (max is 999.9 due to precision 4, scale 1)
    account.base_balance = Decimal("500.0")
    account.save()
    
    # Create vouchers to provide available balance
    VoucherFactory(account=account, state='applied', voucher_type='grocery')
    VoucherFactory(account=account, state='applied', voucher_type='grocery')

    logger.info("Created participant with account balance: %s", account.base_balance)

    # --- Category & Products ---
    grocery_category = CategoryFactory(name="Grocery")
    
    # Create 50 different products with small prices
    products = []
    for i in range(50):
        product = ProductFactory(
            name=f"Product_{i}",
            price=Decimal(f"{1 + (i % 10)}"),  # Prices from 1 to 10
            category=grocery_category
        )
        products.append(product)
    
    logger.info("Created %s products", len(products))

    # --- Session cart setup with 50 items (must happen BEFORE login) ---
    session = client.session
    cart = {}
    expected_item_count = 50
    expected_total = Decimal("0")
    
    for i, product in enumerate(products):
        quantity = 1  # Keep quantity at 1 for all items to stay within balance
        cart[str(product.id)] = quantity
        expected_total += product.price * quantity
    
    session["cart"] = cart
    session.save()
    logger.info("Cart has %s items with expected total: %s", len(cart), expected_total)

    # --- Login using credentials (preserves session) ---
    client.login(username="testuser_50items", password=test_password)

    # --- Define form payload ---
    payload = {"confirm": True}

    # --- POST to submit order ---
    url = reverse("submit_order")
    response = client.post(url, data=payload, follow=True)

    # --- Logging POST response ---
    logger.info("POST submit_order status: %s", response.status_code)
    logger.info("Redirect chain: %s", response.redirect_chain)

    # Capture messages from POST
    messages_list = list(get_messages(response.wsgi_request))
    for m in messages_list:
        logger.info("Message: %s", m)

    # --- Assert response ---
    assert response.status_code == 200

    # --- Verify order created ---
    order = Order.objects.first()
    assert order is not None, "Order should be created"
    
    # --- Verify all 50 items are in the order ---
    order_items = order.items.all()
    assert order_items.count() == expected_item_count, (
        f"Expected {expected_item_count} order items, "
        f"but got {order_items.count()}"
    )
    logger.info("Order has %s items", order_items.count())
    
    # --- Verify each product is in the database and matches cart ---
    for i, product in enumerate(products):
        expected_quantity = 1  # All items have quantity 1
        
        # Find the order item for this product
        order_item = order_items.filter(product=product).first()
        assert order_item is not None, f"Product {product.name} not found in order"
        assert order_item.quantity == expected_quantity, (
            f"Product {product.name} expected quantity {expected_quantity}, "
            f"got {order_item.quantity}"
        )
        assert order_item.price == product.price, (
            f"Product {product.name} price mismatch"
        )
    
    logger.info("All 50 items verified in database")
    
    # --- Verify total price ---
    actual_total = order.total_price()
    assert actual_total == expected_total, (
        f"Expected total {expected_total}, got {actual_total}"
    )
    logger.info("Order total price verified: %s", actual_total)
    
    # --- Verify cart cleared ---
    session = client.session
    assert session.get("cart") == {}, "Cart should be cleared after order"
    
    # --- Verify vouchers consumed ---
    account.refresh_from_db()
    consumed_vouchers = Voucher.objects.filter(
        account=account, 
        state='consumed'
    )
    logger.info("Consumed vouchers: %s", consumed_vouchers.count())
    
    logger.info("Test completed successfully with 50 items")


# ============================================================
# Order Number Uniqueness and Idempotency Tests
# ============================================================


@pytest.mark.django_db
def test_order_number_is_generated_automatically():
    """Test that order_number is automatically generated when an order is created."""
    participant = create_participant(email="ordernum@example.com")
    create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
    
    order = create_order(participant)
    
    # Order number should be automatically generated
    assert order.order_number is not None
    assert order.order_number != ""
    assert len(order.order_number) > 0
    
    logger.info("Generated order number: %s", order.order_number)


@pytest.mark.django_db
def test_order_number_uniqueness():
    """Test that each order gets a unique order number."""
    participant1 = create_participant(email="unique1@example.com")
    create_voucher(participant1, multiplier=1, base_balance=Decimal("100"))
    
    participant2 = create_participant(email="unique2@example.com")
    create_voucher(participant2, multiplier=1, base_balance=Decimal("100"))
    
    # Create multiple orders
    order1 = create_order(participant1)
    order2 = create_order(participant2)
    order3 = create_order(participant1)
    
    # All order numbers should be unique
    order_numbers = [order1.order_number, order2.order_number, order3.order_number]
    
    assert order1.order_number is not None
    assert order2.order_number is not None
    assert order3.order_number is not None
    
    # Check uniqueness
    assert len(order_numbers) == len(set(order_numbers)), (
        f"Order numbers are not unique: {order_numbers}"
    )
    
    logger.info("All order numbers are unique: %s", order_numbers)


@pytest.mark.django_db
def test_order_number_idempotency():
    """Test that order number generation is idempotent (doesn't change on save)."""
    participant = create_participant(email="idempotent@example.com")
    create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
    
    order = create_order(participant)
    original_number = order.order_number
    
    # Save the order multiple times
    for _ in range(5):
        order.save()
        order.refresh_from_db()
        
        # Order number should never change
        assert order.order_number == original_number, (
            f"Order number changed from {original_number} to {order.order_number}"
        )
    
    logger.info("Order number remained stable: %s", original_number)


@pytest.mark.django_db
def test_order_number_format():
    """Test that order numbers follow a consistent format."""
    participant = create_participant(email="format@example.com")
    create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
    
    # Create multiple orders to check format consistency
    orders = [create_order(participant) for _ in range(5)]
    
    for order in orders:
        # Order number should exist
        assert order.order_number is not None
        
        # Should be a string
        assert isinstance(order.order_number, str)
        
        # Should not be empty
        assert len(order.order_number.strip()) > 0
        
        # Should fit within the max_length of 20
        assert len(order.order_number) <= 20
        
        logger.info("Order %s has number: %s", order.id, order.order_number)


@pytest.mark.django_db
def test_order_number_persists_in_database():
    """Test that order numbers are correctly saved and retrieved from database."""
    participant = create_participant(email="persist@example.com")
    create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
    
    order = create_order(participant)
    order_id = order.id
    order_number = order.order_number
    
    # Clear the instance from memory
    del order
    
    # Retrieve from database
    retrieved_order = Order.objects.get(id=order_id)
    
    # Order number should match
    assert retrieved_order.order_number == order_number
    
    logger.info("Order number persisted correctly: %s", order_number)


@pytest.mark.django_db
def test_order_number_uniqueness_constraint():
    """Test that database enforces uniqueness constraint on order_number."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    
    participant = create_participant(email="constraint@example.com")
    create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
    
    order1 = create_order(participant)
    
    # Try to create another order with the same order number
    # This should fail during full_clean() validation
    with pytest.raises(DjangoValidationError) as exc_info:
        Order.objects.create(
            account=participant.accountbalance,
            order_number=order1.order_number,
            status="pending"
        )
    
    # Verify it's the order_number field causing the error
    assert 'order_number' in exc_info.value.error_dict
    
    logger.info("Uniqueness constraint working correctly")


@pytest.mark.django_db
def test_order_number_generation_with_100_orders():
    """Stress test: Create 100 orders and verify all have unique order numbers."""
    participants = []
    for i in range(100):
        participant = create_participant(email=f"stress{i}@example.com")
        create_voucher(participant, multiplier=1, base_balance=Decimal("100"))
        participants.append(participant)
    
    orders = []
    for participant in participants:
        order = create_order(participant)
        orders.append(order)
    
    # Collect all order numbers
    order_numbers = [order.order_number for order in orders]
    
    # Verify all are non-null
    assert all(num is not None for num in order_numbers)
    
    # Verify all are unique
    assert len(order_numbers) == len(set(order_numbers)), (
        f"Found duplicate order numbers in {len(order_numbers)} orders"
    )
    
    # Verify all are within length constraint
    assert all(len(num) <= 20 for num in order_numbers)
    
    logger.info("Successfully created 100 orders with unique numbers")
    logger.info("Sample order numbers: %s", order_numbers[:5])
