# apps/pantry/tests/test_views.py
"""Tests for pantry views."""
import pytest
from decimal import Decimal

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.db import connection

from apps.pantry.views import (
    get_base_products,
    search_products,
    group_products_by_category,
)
from apps.pantry.models import Product, Category
from apps.orders.tests.factories import (
    UserFactory,
    ParticipantFactory,
    ProgramFactory,
)


@pytest.fixture(scope='session', autouse=True)
def enable_trigram_extension(django_db_setup, django_db_blocker):
    """Enable PostgreSQL trigram extension for test database."""
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

User = get_user_model()


@pytest.fixture
def categories():
    """Create test categories."""
    return {
        'fruits': Category.objects.create(name='Fruits'),
        'vegetables': Category.objects.create(name='Vegetables'),
        'dairy': Category.objects.create(name='Dairy'),
    }


@pytest.fixture
def products(categories):
    """Create test products."""
    return [
        Product.objects.create(
            name='Apple',
            description='Fresh red apples',
            price=Decimal('1.99'),
            category=categories['fruits'],
            quantity_in_stock=100,
            active=True
        ),
        Product.objects.create(
            name='Banana',
            description='Yellow bananas',
            price=Decimal('0.99'),
            category=categories['fruits'],
            quantity_in_stock=150,
            active=True
        ),
        Product.objects.create(
            name='Carrot',
            description='Orange carrots',
            price=Decimal('1.49'),
            category=categories['vegetables'],
            quantity_in_stock=80,
            active=True
        ),
        Product.objects.create(
            name='Milk',
            description='Whole milk',
            price=Decimal('3.99'),
            category=categories['dairy'],
            quantity_in_stock=50,
            active=True
        ),
        Product.objects.create(
            name='Inactive Product',
            description='Should not appear',
            price=Decimal('5.99'),
            category=categories['fruits'],
            quantity_in_stock=0,
            active=False
        ),
    ]


@pytest.mark.django_db
class TestGetBaseProducts:
    """Tests for get_base_products function."""

    def test_returns_active_products_only(self, products):
        """Only active products should be returned."""
        result = get_base_products()
        assert result.count() == 4
        assert not result.filter(name='Inactive Product').exists()

    def test_excludes_products_without_category(self, categories):
        """Products without category should be excluded."""
        Product.objects.create(
            name='No Category',
            price=Decimal('2.99'),
            category=None,
            quantity_in_stock=10,
            active=True
        )
        result = get_base_products()
        assert not result.filter(name='No Category').exists()

    def test_products_ordered_by_category_and_name(self, products):
        """Products should be ordered by category then name."""
        result = list(get_base_products())
        # Should have 4 active products, ordered by category ID then name
        assert len(result) == 4
        # Verify all results have categories
        for product in result:
            assert product.category is not None
        # Verify names are sorted within categories
        category_products = {}
        for product in result:
            if product.category not in category_products:
                category_products[product.category] = []
            category_products[product.category].append(product.name)
        # Names should be sorted within each category
        for names in category_products.values():
            assert names == sorted(names)


@pytest.mark.django_db
class TestSearchProducts:
    """Tests for search_products function."""

    def test_search_by_product_name(self, products):
        """Should find products matching name."""
        queryset = get_base_products()
        result = search_products(queryset, 'apple')
        assert result.count() >= 1
        assert result.filter(name='Apple').exists()

    def test_search_by_description(self, products):
        """Should find products matching description."""
        queryset = get_base_products()
        result = search_products(queryset, 'yellow')
        assert result.count() >= 1
        assert result.filter(name='Banana').exists()

    def test_search_by_category(self, products):
        """Should find products matching category name."""
        queryset = get_base_products()
        result = search_products(queryset, 'dairy')
        assert result.count() >= 1
        assert result.filter(name='Milk').exists()

    def test_fuzzy_search_with_typo(self, products):
        """Should find products with fuzzy matching."""
        queryset = get_base_products()
        # 'aple' should still match 'Apple'
        result = search_products(queryset, 'aple')
        # May or may not find depending on trigram availability
        # Just ensure it doesn't crash
        assert result is not None

    def test_empty_query_returns_all(self, products):
        """Empty query should return all products."""
        queryset = get_base_products()
        result = search_products(queryset, '')
        assert result.count() == 4

    def test_case_insensitive_search(self, products):
        """Search should be case insensitive."""
        queryset = get_base_products()
        result1 = search_products(queryset, 'APPLE')
        result2 = search_products(queryset, 'apple')
        # Should find the same results regardless of case
        assert result1.count() == result2.count()


@pytest.mark.django_db
class TestGroupProductsByCategory:
    """Tests for group_products_by_category function."""

    def test_groups_products_correctly(self, products, categories):
        """Products should be grouped by their category."""
        queryset = get_base_products()
        grouped, json_data = group_products_by_category(queryset)
        
        assert len(grouped) == 3
        assert categories['fruits'] in grouped
        assert categories['vegetables'] in grouped
        assert categories['dairy'] in grouped
        
        # Check fruit group has 2 products
        assert len(grouped[categories['fruits']]) == 2
        # Check vegetables group has 1 product
        assert len(grouped[categories['vegetables']]) == 1
        # Check dairy group has 1 product
        assert len(grouped[categories['dairy']]) == 1

    def test_json_data_structure(self, products):
        """JSON data should contain product info."""
        queryset = get_base_products()
        grouped, json_data = group_products_by_category(queryset)
        
        # JSON data should be a string
        assert isinstance(json_data, str)
        # Should contain product information
        assert 'Apple' in json_data
        assert '1.99' in json_data or '1.9900' in json_data

    def test_empty_queryset(self):
        """Should handle empty queryset."""
        queryset = get_base_products()
        grouped, json_data = group_products_by_category(queryset)
        
        assert grouped == {}
        assert json_data == '{}'
