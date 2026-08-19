"""
Tests for apps.pantry.utils.product_lifecycle — auto-deactivation of
zero-stock products (Issue #97).

Business rules verified:
  1. An active product at zero stock is deactivated.
  2. Products above zero are left untouched.
  3. Already-inactive products are not touched or reported again.
  4. `product_ids` scopes the check; omitting it sweeps every product
     (the periodic safety-net path).
  5. Restocking a deactivated product does NOT auto-reactivate it —
     reactivation is always an explicit staff action.
  6. The periodic task (apps.pantry.tasks.product_lifecycle) delegates
     to the same utility as a catch-all sweep.
"""
import pytest

from apps.pantry.tasks.product_lifecycle import deactivate_zero_stock_products
from apps.pantry.tests.factories import ProductFactory
from apps.pantry.utils.product_lifecycle import deactivate_out_of_stock_products

pytestmark = pytest.mark.django_db


class TestDeactivateOutOfStockProducts:

    def test_deactivates_active_product_at_zero_stock(self):
        product = ProductFactory(quantity_in_stock=0, active=True)

        deactivated = deactivate_out_of_stock_products()

        product.refresh_from_db()
        assert product.active is False
        assert deactivated == [(product.id, product.name)]

    def test_leaves_in_stock_products_active(self):
        product = ProductFactory(quantity_in_stock=5, active=True)

        deactivated = deactivate_out_of_stock_products()

        product.refresh_from_db()
        assert product.active is True
        assert deactivated == []

    def test_does_not_report_already_inactive_product(self):
        ProductFactory(quantity_in_stock=0, active=False)

        deactivated = deactivate_out_of_stock_products()

        assert deactivated == []

    def test_product_ids_scopes_the_check(self):
        """Passing product_ids should ignore other zero-stock products entirely."""
        in_scope = ProductFactory(quantity_in_stock=0, active=True)
        out_of_scope = ProductFactory(quantity_in_stock=0, active=True)

        deactivated = deactivate_out_of_stock_products(product_ids=[in_scope.id])

        in_scope.refresh_from_db()
        out_of_scope.refresh_from_db()
        assert in_scope.active is False
        assert out_of_scope.active is True, "Products outside product_ids must be untouched"
        assert deactivated == [(in_scope.id, in_scope.name)]

    def test_omitting_product_ids_sweeps_every_product(self):
        """The periodic safety-net call (no product_ids) catches every zero-stock product."""
        first = ProductFactory(quantity_in_stock=0, active=True)
        second = ProductFactory(quantity_in_stock=0, active=True)

        deactivated = deactivate_out_of_stock_products()

        first.refresh_from_db()
        second.refresh_from_db()
        assert first.active is False
        assert second.active is False
        assert {pid for pid, _ in deactivated} == {first.id, second.id}

    def test_restocking_does_not_auto_reactivate(self):
        """Reactivation is always an explicit staff action, never automatic."""
        product = ProductFactory(quantity_in_stock=0, active=True)
        deactivate_out_of_stock_products()
        product.refresh_from_db()
        assert product.active is False

        product.quantity_in_stock = 10
        product.save(update_fields=['quantity_in_stock'])

        product.refresh_from_db()
        assert product.active is False, "Restocking must not silently reactivate a product"


class TestDeactivateZeroStockProductsTask:

    def test_task_deactivates_zero_stock_products(self):
        product = ProductFactory(quantity_in_stock=0, active=True)

        deactivate_zero_stock_products()

        product.refresh_from_db()
        assert product.active is False

    def test_task_is_a_noop_when_nothing_is_out_of_stock(self):
        product = ProductFactory(quantity_in_stock=5, active=True)

        deactivate_zero_stock_products()

        product.refresh_from_db()
        assert product.active is True
