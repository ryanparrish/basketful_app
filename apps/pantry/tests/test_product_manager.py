"""
DEPRECATED: This file has been split into focused test modules.

The tests from this file have been reorganized into:
- test_category_limits.py: Basic category limit enforcement
- test_limit_scopes.py: Limit scope tests (per_household, per_adult, etc.)
- test_subcategory_limits.py: Subcategory and category-level limits
- test_limit_edge_cases.py: Edge cases and special scenarios

This file is kept temporarily for backwards compatibility.
It will be removed in a future release.

To run the tests, use one of the new test files:
    pytest apps/pantry/tests/test_category_limits.py
    pytest apps/pantry/tests/test_limit_scopes.py
    pytest apps/pantry/tests/test_subcategory_limits.py
    pytest apps/pantry/tests/test_limit_edge_cases.py

Or run all at once:
    pytest apps/pantry/tests/test_*limit*.py
"""

# This file intentionally left empty to avoid import errors
# All tests have been moved to separate, focused test modules
