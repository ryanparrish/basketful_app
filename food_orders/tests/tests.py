# tests/test_models_and_forms_pytest.py

"""
================================================================================
Pytest Tests for Models, Forms, and Validation Logic
================================================================================

This file contains tests for various parts of the application, including:
- Order formset validation (e.g., weight and category spending limits).
- Order model price calculations.
- Voucher balance logic.
- Model relationships and validation constraints.

Key Pytest Concepts Used:
-------------------------
- **Fixtures (`@pytest.fixture`)**: Each group of tests uses dedicated fixtures
  to create a clean, specific state (e.g., an order with specific items, a
  participant with a known voucher balance). This makes tests independent and
  easy to understand.

- **`pytest.raises`**: A context manager used to assert that a specific
  piece of code raises an expected exception, which is ideal for testing
  model validation.

- **Direct Factory Usage**: Instead of class-based helper methods, tests use
  the factories directly, making the test setup more explicit and readable.
"""

# ============================================================
# Imports
# ============================================================

# --- Standard Library Imports ---
from decimal import Decimal

# --- Third-Party Imports ---
import pytest
import factory  # Used to define a new factory for the Program model
from django.core.exceptions import ValidationError

# --- Local Application Imports ---
# --- Models needed for testing ---
from food_orders.models import (
    Program,
    Product,
    OrderItem,
)
# --- Factories and helpers from our shared test utilities ---
from factories import (
    CategoryFactory,
    ParticipantFactory,
    ProgramFactory,
)


# ============================================================
# Participant, Program, and Validation Tests
# ============================================================

@pytest.mark.django_db
def test_participant_program_relationship():
    """Tests the foreign key relationship between Participant and Program."""
    # --- ARRANGE ---
    # --- Use our new ProgramFactory to create a program ---
    program = ProgramFactory(name="Wednesday Class")
    # --- Create a participant and link them to the program ---
    participant = ParticipantFactory(name="Jane Doe", program=program)

    # --- ASSERT ---
    # --- Test the forward relationship (participant -> program) ---
    assert participant.program == program
    # --- Test the reverse relationship (program -> participants) ---
    assert participant in program.participant_set.all()


@pytest.mark.django_db
def test_negative_product_quantity_raises_validation_error():
    """
    Tests the model-level validation to ensure a product cannot be created
    with a negative stock quantity.
    """
    # --- ARRANGE ---
    # --- Create a product instance in memory with an invalid quantity ---
    product = Product(
        name="Bad Cereal",
        price=Decimal("3.00"),
        quantity_in_stock=-10,  # Invalid value
        category=CategoryFactory(),
    )

    # --- ACT & ASSERT ---
    # --- Use `pytest.raises` as a context manager ---
    # --- It asserts that a `ValidationError` must be raised inside this block. ---
    with pytest.raises(ValidationError):
        # --- `full_clean()` runs all model validation checks ---
        product.full_clean()