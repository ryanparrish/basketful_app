import pytest
from decimal import Decimal
from django.core.management import call_command


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Custom database setup to handle circular migration dependencies.
    
    This fixture runs migrations with --run-syncdb to create tables
    from models directly, bypassing the circular dependency issue in
    the initial migrations.
    """
    with django_db_blocker.unblock():
        # Create all tables from current models
        call_command('migrate', '--run-syncdb', verbosity=0)
        # Mark all migrations as applied
        call_command('migrate', '--fake', verbosity=0)


@pytest.fixture
def order_with_items_setup(db):
    """
    Create an order with two items for testing price calculations.
    
    Returns a dict with:
        - participant: Participant instance
        - account: AccountBalance instance
        - category: Category instance
        - product1: Product instance ($2.50)
        - product2: Product instance ($3.00)
        - order: Order instance
        - item1: OrderItem instance (3 * $2.50 = $7.50)
        - item2: OrderItem instance (2 * $3.00 = $6.00)
    """
    from apps.orders.models import Order, OrderItem
    from apps.pantry.models import Category, Product
    from apps.account.models import Participant, AccountBalance
    
    # Create participant and account
    participant = Participant.objects.create(
        name="Test Participant",
        email="test@example.com",
        active=True
    )
    # Use get_or_create to avoid conflict with signal
    account, _ = AccountBalance.objects.get_or_create(
        participant=participant,
        defaults={'base_balance': Decimal("100.0")}
    )
    
    # Create category and products
    category = Category.objects.create(name="Grocery")
    product1 = Product.objects.create(
        name="Product 1",
        price=Decimal("2.50"),
        category=category,
        description="Test product 1",
        quantity_in_stock=100
    )
    product2 = Product.objects.create(
        name="Product 2",
        price=Decimal("3.00"),
        category=category,
        description="Test product 2",
        quantity_in_stock=100
    )
    
    # Create order
    order = Order.objects.create(
        account=account,
        status="pending"
    )
    
    # Create order items
    item1 = OrderItem.objects.create(
        order=order,
        product=product1,
        quantity=3,
        price=product1.price
    )
    item2 = OrderItem.objects.create(
        order=order,
        product=product2,
        quantity=2,
        price=product2.price
    )
    
    return {
        "participant": participant,
        "account": account,
        "category": category,
        "product1": product1,
        "product2": product2,
        "order": order,
        "item1": item1,
        "item2": item2,
    }

