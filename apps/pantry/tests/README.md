# Pantry Tests

This directory contains test suites for the pantry application.

## Test File Organization

### Product Limit Validation Tests

The product limit validation tests have been refactored into focused, maintainable modules:

#### `test_category_limits.py`
Basic category limit enforcement tests:
- `test_meat_weight_limit_exceeded` - Validates that exceeding limits raises errors
- `test_meat_within_limit` - Validates that orders within limits pass
- `test_non_meat_products_unaffected` - Products without limits are unrestricted
- `test_zero_quantity_does_not_trigger_validation` - Zero quantities are ignored

#### `test_limit_scopes.py`
Tests for different limit scope types:
- `test_per_household_scope` - Limit multiplied by household size
- `test_per_adult_scope` - Limit multiplied by number of adults
- `test_per_child_scope` - Limit multiplied by number of children
- `test_per_infant_scope` - Limit multiplied by diaper_count
- `test_per_order_scope` - Fixed limit per order (not multiplied)

#### `test_subcategory_limits.py`
Subcategory and category-level limit enforcement:
- `test_subcategory_limit_enforced` - Subcategories have separate limits
- `test_category_level_limit_aggregates_all_products` - Category limits aggregate all products

#### `test_limit_edge_cases.py`
Edge cases and special scenarios:
- `test_zero_infants_with_per_infant_scope` - Zero infants = zero allowed
- `test_zero_children_with_per_child_scope` - Zero children = zero allowed
- `test_multiple_products_same_category_aggregate` - Multiple products aggregate correctly
- `test_no_limit_set_allows_unlimited` - Categories without limits are unlimited
- `test_mixed_limited_and_unlimited_products` - Mixed scenarios work correctly

#### `test_limit_uniqueness.py`
Tests for product limit uniqueness and isolation:
- `test_different_categories_have_independent_limits` - Different categories don't interfere
- `test_subcategories_have_independent_limits_from_parent_category` - Subcategories independent from parent
- `test_multiple_subcategories_each_have_unique_limits` - Multiple subcategories are isolated
- `test_frozen_meat_limit_does_not_enforce_regular_meat_limit` - Frozen vs fresh meat example
- `test_same_limit_value_different_categories_enforced_separately` - Same limit value, different enforcement
- `test_different_scopes_on_same_category_are_independent` - Different scopes work independently
- `test_per_adult_scope_unique_to_category` - per_adult scope calculated independently per category
- `test_per_child_scope_unique_to_subcategory` - per_child scope calculated independently per subcategory
- `test_per_infant_scope_unique_to_subcategory` - per_infant scope calculated independently per subcategory
- `test_per_household_scope_unique_to_category` - per_household scope calculated independently per category
- `test_per_order_scope_unique_to_subcategory` - per_order scope applied independently per subcategory
- `test_mixed_scopes_across_categories_all_independent` - All scopes work together independently

### View Tests

#### `test_views.py`
Tests for view functions:
- `TestGetBaseProducts` - Base product queryset tests
- `TestSearchProducts` - Product search and fuzzy matching tests
- `TestGroupProductsByCategory` - Product grouping tests

### Other Tests

#### `tests.py`
General pantry-related tests:
- Participant and program relationship tests
- Product validation tests

#### `test_product_manager.py` (DEPRECATED)
This file has been split into the focused test modules above. It remains as a placeholder with documentation about the refactoring. **New tests should not be added here.**

## Running Tests

Run all pantry tests:
```bash
pytest apps/pantry/tests/
```

Run specific test categories:
```bash
# All limit-related tests
pytest apps/pantry/tests/test_*limit*.py

# Just scope tests
pytest apps/pantry/tests/test_limit_scopes.py

# Just view tests
pytest apps/pantry/tests/test_views.py
```

Run with verbose output:
```bash
pytest apps/pantry/tests/ -v
```

## Test Fixtures

Common fixtures are defined in `conftest.py` and shared across all test files. Key fixtures include:
- `order_formset_setup` - Sets up order with participant and products
- `meat_product_with_manager` - Creates product with category limits

## Adding New Tests

When adding new tests:
1. Choose the appropriate test file based on what you're testing
2. Follow the existing naming conventions
3. Use descriptive test names that explain what is being validated
4. Add docstrings to explain the test scenario
5. Use the `@pytest.mark.django_db` decorator for tests that access the database
