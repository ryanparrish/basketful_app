# Go Fresh Budget Feature Documentation

> Last updated: 2026-07-13

## Overview

The Go Fresh Budget feature provides participants with a dedicated per-order budget for fresh food items from the "Go Fresh" category. Unlike the hygiene balance (which is a percentage of available balance), the Go Fresh budget is a fixed amount based on household size that resets with each order.

**Key Characteristics:**
- Per-order budget that doesn't carry over between orders
- Based on household size thresholds
- Independent calculation (not a percentage of available balance)
- Items count against both Go Fresh budget AND overall available balance
- Protected category that cannot be deleted or renamed

## Feature Components

### 1. GoFreshSettings Singleton Model

**Location:** `apps/account/models.py`

Configurable settings for Go Fresh budgets:

**Fields:**
- `small_household_budget` (Decimal): Budget for households 1-2 people (default: $10.00)
- `medium_household_budget` (Decimal): Budget for households 3-5 people (default: $20.00)
- `large_household_budget` (Decimal): Budget for households 6+ people (default: $25.00)
- `small_threshold` (Integer): Maximum household size for small budget (default: 2)
- `large_threshold` (Integer): Minimum household size for large budget (default: 6)
- `enabled` (Boolean): Enable/disable the feature system-wide (default: True)

**Validation Rules:**
- `small_threshold` must be less than `large_threshold`
- All budget amounts must be positive (> 0)
- Singleton pattern enforced (only one instance can exist)

**Admin Access:**
Navigate to: Admin → Account → Go Fresh Settings

### 2. Balance Calculation

**Location:** `apps/account/utils/balance_utils.py`

The `calculate_go_fresh_balance()` function determines the budget based on household size, then applies the current program-pause multiplier (see below):

```python
def calculate_go_fresh_balance(account_balance) -> Decimal:
    """
    Calculate Go Fresh budget per order based on household size.

    Household size determines a base tier (small/medium/large), and the
    result is multiplied by the current program-pause multiplier (1 unless
    a pause's pre-pause ordering window is currently active).
    """
    ...
    if household_size <= settings.small_threshold:
        base = settings.small_household_budget
    elif household_size >= settings.large_threshold:
        base = settings.large_household_budget
    else:
        base = settings.medium_household_budget

    multiplier = _get_current_pause_multiplier()
    return base * Decimal(multiplier)
```

**Examples with Default Thresholds (no pause multiplier active):**
- 1 person household: $10.00 (small)
- 2 people household: $10.00 (small)
- 3 people household: $20.00 (medium)
- 4 people household: $20.00 (medium)
- 5 people household: $20.00 (medium)
- 6 people household: $25.00 (large)
- 10 people household: $25.00 (large)

### 2a. Program Pause Multiplier

Go Fresh budget is boosted the same way grocery voucher balances are: `_get_current_pause_multiplier()` (also in `apps/account/utils/balance_utils.py`) looks at every non-archived `ProgramPause` and takes the highest `multiplier` property across them (1 if none are currently in their pre-pause ordering window, 2 for a short pause, 3 for an extended pause — see [PROGRAM_PAUSES.md](PROGRAM_PAUSES.md)).

This means a 4-person household's normal $20.00 Go Fresh budget becomes $40.00 during a short pause's 10–14 day pre-pause ordering window, or $60.00 during an extended pause's window. This multiplier is **not documented anywhere else** in this feature's original design — it was added so Go Fresh budgets scale up alongside grocery vouchers when participants are stocking up before a break.

### 3. Category Protection

**Location:** `apps/pantry/admin.py`

Both "Hygiene" and "Go Fresh" categories are protected from modification:

**Protection Mechanisms:**
- Name field becomes read-only in admin when editing protected categories
- Delete button is disabled for protected categories
- Attempting to delete raises `PermissionDenied` with helpful error message
- Lock icon (🔒) displayed in admin list view

**Protected Categories:**
- `hygiene` (case-insensitive)
- `go fresh` (case-insensitive)

### 4. Order Validation

Go Fresh budget is enforced in **three separate places**, each with slightly different wording:

1. **`apps/orders/models.py` — `Order.clean()`** (authoritative, runs on every `Order.save()` via `full_clean()`)
   - Calculates total price of items in the "Go Fresh" category, compares against `account.go_fresh_balance`
   - Only runs the comparison if `go_fresh_balance > 0` (i.e., skips the check entirely when the feature is disabled)
   - On failure, raises `ValidationError`:
     ```
     Go Fresh balance exceeded: $XX.XX > $YY.YY
     ```
   - Also persists the computed `go_fresh_total` onto the order instance (see Order Tracking, below)

2. **`apps/orders/utils/order_validation.py` — `OrderValidation.validate_order_items()`** (used by the Django admin order-item inline and by `OrderOrchestration`'s create-order path in `apps/orders/utils/order_utils.py`)
   - Same threshold check, but raises:
     ```
     Go Fresh items total $XX.XX exceeds Go Fresh balance $YY.YY.
     ```

3. **`apps/orders/api/views.py` — `OrderViewSet.validate_cart()` action** (`POST /api/orders/validate-cart/`, a non-committing preview endpoint used by the React frontends before checkout)
   - Does not raise — instead appends a violation object to the response:
     ```json
     {"type": "balance", "severity": "error", "message": "Go Fresh balance exceeded by $X.XX", "amount_over": X.XX, "grace_allowed": false}
     ```
   - Like the food/hygiene balance checks in this endpoint, an over-budget Go Fresh total can be downgraded to a `"warning"` (grace-allowed) if the overage is within `ProgramSettings.grace_amount`. Go Fresh does not currently get its own grace rule — it shares the program-wide grace allowance.

**Important:** Go Fresh items must pass BOTH validations in every path above:
- Go Fresh-specific budget (per-order limit)
- Overall available balance (weekly limit) — Go Fresh items are counted as `food_items` (anything not in the "Hygiene" category) for this check

### 5. Order Tracking

**Location:** `apps/orders/models.py`

The `Order` model includes a `go_fresh_total` field:

```python
go_fresh_total = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0,
    help_text="Total amount spent on Go Fresh items in this order"
)
```

`Order.clean()` computes and assigns this field during validation. `Order.confirm()` recomputes it and explicitly includes it in `update_fields` (`self.save(update_fields=['status', 'paid', 'go_fresh_total'])`) so the value is persisted at confirmation time, not just held in memory — this is covered by regression tests in `apps/orders/tests/test_go_fresh_validation.py`.

## User Interface

### Dashboard Balance Cards

**Location:** `apps/pantry/templates/food_orders/participant_dashboard.html`

The dashboard displays 4 balance cards in responsive grid:

1. **Full Balance** (Blue/Info) - "Total value of all your vouchers"
2. **Available Balance** (Primary Blue) - "Your balance available for this week's order"
3. **Hygiene Balance** (Orange/Warning) - "Your hygiene product allowance (1/3 of available balance)"
4. **Go Fresh Balance** (Green/Success) - "Your fresh food budget (resets each order)"

**Responsive Layout:**
- Desktop (≥992px): 4 columns
- Tablet (768px-991px): 2 columns
- Mobile (<768px): 1 column (stacked)

### Cart Drawer (Legacy Django Template)

**Location:** `core/templates/pantry/create_order.html` (not under `apps/pantry/templates/`)

This template renders the offcanvas "Your Cart" drawer, but it does **not** display Available/Hygiene/Go Fresh balances — it only lists cart line items and a running total, computed client-side from `allProducts`/`sessionCart` JSON embedded in the page. Submitting the cart POSTs to `/update-cart/` (see below) purely to persist the session cart, then redirects to `review_order`; the response's `balances` payload is not read or rendered anywhere in this template.

**Note:** `apps/pantry/static/js/cart.js` defines a separate `updateCartBalances()` / `syncCartWithServer()` pair that *would* populate `#cart-available-balance`, `#cart-hygiene-balance`, and `#cart-go-fresh-balance` elements in real time — but that script is not `{% static %}`-included by `create_order.html`. It only ships with, and is exercised by, its own Jest test files (`cart.test.js`, `cart-submission.test.js`, etc.) and is effectively dead code against the live template.

### Participant-Frontend Account Page (React)

**Location:** `participant-frontend/src/components/AccountPage.tsx`

The newer React participant app renders all four balances (full, available, hygiene, go_fresh) as colored balance cards, fetched from `GET /account-balances/me/` (see `participant-frontend/src/shared/api/endpoints.ts`). This is where a real-time Go Fresh balance display currently lives in practice.

### Cart AJAX Response

**Location:** `apps/pantry/views.py` - `update_cart()` view

The cart update endpoint returns balance data:

```json
{
  "status": "ok",
  "balances": {
    "full_balance": "125.00",
    "available_balance": "125.00",
    "hygiene_balance": "41.67",
    "go_fresh_balance": "20.00"
  }
}
```

## Database Schema

### Migrations

1. **Account App Migration:** `0004_add_go_fresh_settings.py`
   - Creates `GoFreshSettings` model
   - Seeds initial settings (pk=1)
   - Checks for "Go Fresh" category existence
   - Creates custom permission: `can_view_go_fresh_analytics`

2. **Orders App Migration:** `0008_add_go_fresh_total.py`
   - Adds `go_fresh_total` field to `Order` model
   - Default value: 0

### Custom Permission

**Permission:** `account.can_view_go_fresh_analytics`

**Purpose:** Controls access to Go Fresh analytics dashboard (future feature)

**Assignment:** Via Django admin → Users → Permissions

## Testing

### Test Files

1. **Balance Calculations:** `apps/account/tests/test_go_fresh_balance.py`
   - Tests for all household size tiers
   - Settings validation tests
   - Singleton enforcement tests
   - Custom threshold configuration tests

2. **Order Validation:** `apps/orders/tests/test_go_fresh_validation.py`
   - Within limit scenarios
   - Exceeding Go Fresh limit
   - Exceeding available balance
   - Mixed cart validation
   - Edge cases (disabled feature, no category, etc.)

3. **Category Protection:** `apps/pantry/tests/test_category_protection.py`
   - Readonly name field tests
   - Delete prevention tests
   - Lock icon display tests
   - Case-insensitive protection tests

### Running Tests

```bash
# All Go Fresh tests
pytest apps/account/tests/test_go_fresh_balance.py apps/orders/tests/test_go_fresh_validation.py apps/pantry/tests/test_category_protection.py -v

# Specific test class
pytest apps/account/tests/test_go_fresh_balance.py::TestGoFreshBalanceCalculations -v

# Single test
pytest apps/account/tests/test_go_fresh_balance.py::TestGoFreshBalanceCalculations::test_small_household_1_person -v
```

## Configuration

### Modifying Go Fresh Budgets

1. Navigate to Django Admin
2. Go to: Account → Go Fresh Settings
3. Modify budget amounts or thresholds
4. Click "Save"

**Impact Warning:** Changes take effect immediately for all future orders.

### Disabling Go Fresh Feature

1. Navigate to Django Admin → Account → Go Fresh Settings
2. Uncheck "Enabled"
3. Click "Save"

**Effect:** All participants will see $0.00 Go Fresh balance, and no Go Fresh validation will be enforced (but items still count against available balance).

### Creating the Go Fresh Category

If the "Go Fresh" category doesn't exist:

1. Navigate to Django Admin → Pantry → Categories
2. Click "Add Category"
3. Enter name: "Go Fresh" (exact spelling, case-insensitive)
4. Click "Save"
5. The category is now protected and cannot be deleted

## Per-Order Reset Behavior

**Key Concept:** Unlike available balance (which accumulates weekly vouchers), Go Fresh budget resets with each order.

**Example Scenario:**
- Participant has 4-person household → $20 Go Fresh budget
- **Order 1:** Uses $5 of Go Fresh items
  - Remaining for this order: $15 (not carried over)
- **Order 2:** Fresh $20 Go Fresh budget
  - Can use full $20 again

**Rationale:** Ensures consistent access to fresh food each time a participant shops, regardless of previous order patterns.

## Troubleshooting

### "Go Fresh category not found" Warning During Migration

**Cause:** The "Go Fresh" category doesn't exist in the database.

**Solution:** Create the category manually:
1. Django Admin → Pantry → Categories
2. Add Category with name "Go Fresh"
3. Migration warning will not appear on future migrations

### Go Fresh Balance Shows $0.00

**Possible Causes:**
1. Feature is disabled → Check GoFreshSettings.enabled
2. Participant has no AccountBalance → Check participant setup
3. Settings misconfigured → Check threshold values

### Order Fails with "Go Fresh balance exceeded" Error

**Expected Behavior:** Participant has exceeded their per-order Go Fresh budget.

**Resolution:**
1. Remove some Go Fresh items from cart
2. Check participant's household size matches expected budget
3. Verify GoFreshSettings configuration is correct

### Protected Category Can Be Modified

**Issue:** Category name is editable or can be deleted.

**Check:**
1. Verify category name is exactly "Go Fresh" or "Hygiene" (case-insensitive)
2. Check `PROTECTED_CATEGORIES` constant in `apps/pantry/admin.py`
3. Clear browser cache and refresh admin

## Future Enhancements

### Go Fresh Analytics Dashboard (Planned)

**Features:**
- Date range filtering (reusing redeemed report logic)
- Total Go Fresh spending across all orders
- Average spending per order by household size
- Budget utilization percentage
- Top Go Fresh products
- CSV/PDF export with customer numbers
- Charts with distinct colors per household size
- 1-hour cache with manual refresh option
- Custom permission: `account.can_view_go_fresh_analytics`

**Location (When Implemented):** `apps/account/views.py` and templates

## Related Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture including balance calculations
- [ORDER_WINDOW_FEATURE.md](ORDER_WINDOW_FEATURE.md) - Related ordering constraints
- [CUSTOMER_NUMBER_SYSTEM.md](CUSTOMER_NUMBER_SYSTEM.md) - Participant identification

## Technical Notes

### Why Not a Percentage Like Hygiene?

Hygiene balance is 1/3 of available balance because hygiene needs scale with overall shopping budget. Fresh food needs are more consistent regardless of overall budget, so a fixed per-order amount based on household size provides more predictable access.

### Why Per-Order Reset?

This ensures every shopping trip includes fresh food access, preventing scenarios where participants "save up" Go Fresh budget but then can't use it effectively for perishable items.

### Database Performance

- `go_fresh_balance` is a property (calculated on-demand, not stored)
- `go_fresh_total` is stored on Order for efficient reporting queries
- GoFreshSettings singleton uses `pk=1` for predictable queries
- Category protection checks are minimal (lookup by name.lower())

## Changelog

**Documentation audit** (2026-07-13)
- Corrected: `calculate_go_fresh_balance()` also applies the program-pause multiplier (`_get_current_pause_multiplier()`) — previously undocumented.
- Corrected: Order validation actually happens in three places with different message wording (`Order.clean()`, `OrderValidation.validate_order_items()`, and the `validate-cart` API action), not just `Order.clean()`.
- Corrected: `create_order.html` lives at `core/templates/pantry/create_order.html`, not under `apps/pantry/templates/`, and its cart drawer does not display real-time balances — `cart.js`'s balance-display functions are not wired into the live template.
- Added: participant-frontend React `AccountPage.tsx` as the current real-time balance display surface.

**Version 1.0.0** (January 30, 2026)
- Initial implementation
- GoFreshSettings singleton model
- Category protection for "Go Fresh" and "Hygiene"
- Dashboard balance cards (4-card responsive layout)
- Cart drawer real-time balance updates
- Order validation with dual balance checks
- Comprehensive test suite
- Database migrations with category existence check
