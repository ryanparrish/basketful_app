# food_orders/utils/test_helpers.py

"""
================================================================================
Test Helpers, Factories, and Utilities for the food_orders App
================================================================================

This file consolidates all necessary components for robust testing into a single,
well-documented module. It includes:

1.  **Factory Boy Factories**: For creating consistent, reusable, and complex
    Django model instances for tests (e.g., Product, Participant, Order).

2.  **Logging Utilities**: A shared logger and helper functions to provide
    detailed output during test runs, which is invaluable for debugging complex
    interactions, such as voucher logic.

3.  **Base Test Data Mixin**: A convenient mixin class (`BaseTestDataMixin`) that
    test classes can inherit from. It uses the factories to provide simple helper
    methods for setting up common test data (e.g., `create_product(...)`) and
    other useful utilities for form testing.

By centralizing these tools, we ensure consistency and reduce boilerplate code
across all test files within the application.
"""

# ============================================================
# Imports
# ============================================================
# --- Standard Library Imports ---
from decimal import Decimal
import logging

# --- Third-Party Imports ---
import factory  # The core library for building model factories.

# --- Local Application Imports ---
# Import all the models that we will be creating factories for.
from food_orders.models import (
    Category,
    Product,
    Participant,
    Voucher,
    Order,
    OrderItem,
    AccountBalance,
    Program,
    ProductManager,
    Subcategory,
    VoucherSetting
)
# Import the custom formset used in the application to replicate its behavior in tests.
from food_orders.forms import OrderItemInlineFormSet

# ============================================================
# Factory Boy Factories
# ============================================================
"""
Factories provide a powerful way to create instances of Django models for testing.
They abstract away the details of model creation, allowing you to generate test
data that is both consistent and easy to read.
"""

# --- Factory for the Category Model ---
class CategoryFactory(factory.django.DjangoModelFactory):
    """
    Creates Category model instances.
    Each category will have a unique name by default.
    """

    class Meta:
        # --- Link this factory to the Category Django model ---
        model = Category

    # --- Define the 'name' field for the Category model ---
    # `factory.Sequence` generates unique values for each instance created.
    # The lambda function `lambda n: ...` takes the sequence number `n`
    # and generates a string like "Category 0", "Category 1", etc.
    name = factory.Sequence(lambda n: f"Category {n}")

# --- Factory for the Product Model ---
class ProductFactory(factory.django.DjangoModelFactory):
    """
    Creates Product model instances.
    Each product will have a unique name, a default price, a default stock
    quantity, and an associated Category (created automatically).
    """

    class Meta:
        # --- Link this factory to the Product Django model ---
        model = Product

    # --- Define the fields for the Product model ---
    # `factory.Sequence` ensures each product gets a unique name.
    name = factory.Sequence(lambda n: f"Product {n}")

    # --- Set a default price. Use Decimal for monetary values to avoid floating-point errors ---
    price = Decimal("50.00")

    # `factory.SubFactory` is used for ForeignKey relationships.
    # When a Product is created with this factory, it will automatically
    # create a corresponding Category instance using `CategoryFactory`.
    category = factory.SubFactory(CategoryFactory)

    # --- Set a default quantity for the product's stock ---
    quantity_in_stock = 10


# --- Factory for the Participant Model ---
class ParticipantFactory(factory.django.DjangoModelFactory):
    """
    Creates Participant model instances.
    This factory uses the `Faker` library to generate realistic-looking
    names and emails. It also includes a post-generation hook to automatically
    create an associated AccountBalance.
    """

    class Meta:
        # --- Link this factory to the Participant Django model ---
        model = Participant

    # --- Use `factory.Faker` to generate realistic fake data ---
    # 'name' will generate a random person's name (e.g., "John Doe").
    name = factory.Faker("name")
    # 'email' will generate a random, validly formatted email address.
    email = factory.Faker("email")

    # --- Set default values for other participant fields ---
    adults = 1
    children = 0
    diaper_count = 0

    # --- `post_generation` hooks run after the model instance is created and saved ---
    @factory.post_generation
    def account_balance(self, create, extracted, **kwargs):
        """
        A hook to automatically create an `AccountBalance` for every new Participant.
        This ensures that any created Participant always has the necessary related
        AccountBalance object, simplifying test setup.
        """
        # --- The 'create' argument is True if the factory was called to create and save ---
        # We check this to avoid running the hook for "build" strategies (in-memory only).
        if not create:
            return  # Do nothing if the instance isn't being saved to the database.

        # --- Create and link the AccountBalance instance ---
        # The `self` here refers to the Participant instance that was just created.
        AccountBalance.objects.filter(
            participant=self).update(base_balance=100)

# --- Factory for the Voucher Model ---

class VoucherSettingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VoucherSetting

    active = True
    adult_amount = Decimal("20.00")
    child_amount = Decimal("12.50")
    infant_modifier = Decimal("2.50")  # e.g., multiplier for diapers

class VoucherFactory(factory.django.DjangoModelFactory):
    """
    Factory for creating Voucher instances.
    Allows specifying:
    - participant: automatically uses participant.accountbalance
    - base_balance: sets the related account's balance
    - multiplier: voucher multiplier
    """

    class Meta:
        model = Voucher

    multiplier = 1  # default multiplier

    @factory.post_generation
    def set_participant_and_balance(self, create, extracted, **kwargs):
        """
        Post-generation hook to handle:
        - participant: links voucher to participant's account
        - base_balance: sets the account's base_balance
        """
        if not create:
            return

        # Handle participant
        participant = kwargs.pop("participant", None)
        if participant:
            self.account = participant.accountbalance

        # Handle base_balance
        base_balance = kwargs.pop("base_balance", None)
        if base_balance is not None:
            self.account.base_balance = base_balance
            self.account.save()

# --- Factory for the Order Model ---
class OrderFactory(factory.django.DjangoModelFactory):
    """
    Creates Order model instances.
    Each Order is linked to an AccountBalance and has a default status.
    """

    class Meta:
        # --- Link this factory to the Order Django model ---
        model = Order


    # --- Set a default status for newly created orders ---
    status_type = "pending"

# --- Factory for the OrderItem Model ---
class OrderItemFactory(factory.django.DjangoModelFactory):
    """
    Creates OrderItem model instances.
    An OrderItem connects a Product to an Order with a specific quantity.
    """

    class Meta:
        # --- Link this factory to the OrderItem Django model ---
        model = OrderItem

    # --- Use SubFactories to link to an Order and a Product ---
    # This will automatically create an Order and a Product if they are not provided.
    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)

    # --- Set a default quantity for the order item ---
    quantity = 1
class ProgramFactory(factory.django.DjangoModelFactory):
    """Factory for creating Program model instances."""
    class Meta:
        model = Program

    name = factory.Sequence(lambda n: f"Program {n}")
    MeetingDay = "Wednesday"
    meeting_time = "10:00:00"

class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")

class SubcategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Subcategory

    name = factory.Sequence(lambda n: f"Subcategory {n}")
    category = factory.SubFactory(CategoryFactory)

class ProductManagerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductManager

    name = factory.Sequence(lambda n: f"Product Manager {n}")
    category = factory.SubFactory(CategoryFactory)
    subcategory = None  # you can override in tests if needed
    notes = factory.Faker("sentence")
    limit = 2
    limit_scope = "per_household"

from django.contrib.auth.models import User

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    password = factory.PostGenerationMethodCall("set_password", "password123")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
