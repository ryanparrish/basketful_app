# Cart + Search Bug Report

## Issue Summary
**Bug**: When using the search function, cart items disappear from the cart UI if they don't match the search query.

## Problem Description

### User Experience
1. User adds items to cart: Apple, Banana, Carrot
2. User searches for "apple"
3. **BUG**: Only Apple shows in cart drawer, Banana and Carrot disappear
4. Cart icon still shows correct count (3 items)
5. Cart total only shows Apple's price
6. User is confused - items seem to have vanished

### Root Cause

**File**: `apps/pantry/templates/food_orders/create_order.html`

When search is performed:
1. Django filters products on server side
2. Only search results are passed to JavaScript as `products` object
3. Cart rendering code loops through cart items and checks `if (!product) continue;`
4. Items not in `products` object are skipped during rendering
5. Cart total only includes visible products

**Code Location** (line ~210):
```javascript
for (const [productId, quantity] of Object.entries(cart)) {
  const product = products[productId];
  if (!product) continue;  // ← SKIPS ITEMS NOT IN SEARCH RESULTS
  
  // Render cart item...
}
```

## Test Results

Created **12 tests** in `cart-search-bug.test.js`:

✅ All tests pass, confirming the bug:

1. **Cart retains items** but they're hidden from UI ✓
2. **Cart items skipped** when not in search results ✓  
3. **Cart total incorrect** when products filtered ✓
4. **Cart persistence** works but UI doesn't show all items ✓
5. **Empty search** shows $0.00 total but cart icon shows items ✓
6. **Removing hidden items** works but user can't see them ✓

## Impact

### Severity: HIGH
- **User Confusion**: Items appear to vanish
- **Wrong Total**: Cart shows incorrect price
- **Trust Issues**: Users don't know if items are still there
- **Accidental Removal**: Users might re-search and re-add items

### Affected Scenarios
- ✗ Searching for products
- ✗ Filtering by category (if category filter hides products)
- ✗ Any page reload with query parameters

## Proposed Solutions

### Option 1: Pass Full Product List (RECOMMENDED)
Modify `product_view()` to always pass complete product list for cart rendering:

```python
# apps/pantry/views.py
def product_view(request):
    query = request.GET.get("q", "")
    
    # Get base products
    all_products = get_base_products()
    
    # Filter for display
    if query:
        filtered_products = search_products(all_products, query)
    else:
        filtered_products = all_products
    
    # Group filtered products for display
    products_by_category, _ = group_products_by_category(filtered_products)
    
    # Pass ALL products for cart rendering
    all_products_json = json.dumps({
        str(p.id): {
            'name': p.name,
            'price': float(p.price),
            'category': p.category.name if p.category else ''
        }
        for p in all_products
    })
    
    return render(request, "pantry/create_order.html", {
        "products_by_category": products_by_category,  # Filtered for display
        "products_json": all_products_json,             # Full list for cart
        "query": query,
        "session_cart": json.dumps(session_cart),
    })
```

**Pros**:
- Simple fix
- Cart always shows all items
- Correct totals
- No UI changes needed

**Cons**:
- Slightly more data sent to browser
- Products list includes all products (not a security issue, just more data)

### Option 2: Show Hidden Items Warning
Add UI indicator when cart has items not in current view:

```javascript
function renderCart() {
  // ... existing code ...
  
  // Count hidden items
  let hiddenCount = 0;
  for (const [productId, quantity] of Object.entries(cart)) {
    if (!products[productId]) {
      hiddenCount += quantity;
    }
  }
  
  // Show warning if items are hidden
  if (hiddenCount > 0) {
    const warningLi = document.createElement('li');
    warningLi.className = 'list-group-item list-group-item-warning';
    warningLi.innerHTML = `
      <i class="bi bi-exclamation-triangle"></i>
      ${hiddenCount} item(s) hidden by current search/filter
      <a href="?">Clear search to view all items</a>
    `;
    mobileCartList.insertBefore(warningLi, mobileCartList.firstChild);
  }
}
```

**Pros**:
- Informs user about hidden items
- Provides clear action (clear search)

**Cons**:
- Cart total still wrong
- Still confusing UX
- Requires both server and client changes

### Option 3: Separate Cart Product API
Create dedicated endpoint for cart product data:

```python
@login_required
def cart_products(request):
    """Return product details for items currently in session cart."""
    cart = request.session.get('cart', {})
    product_ids = [int(pid) for pid in cart.keys()]
    
    products = Product.objects.filter(id__in=product_ids)
    products_data = {
        str(p.id): {
            'name': p.name,
            'price': float(p.price),
            'category': p.category.name if p.category else ''
        }
        for p in products
    }
    
    return JsonResponse(products_data)
```

**Pros**:
- Only sends needed product data
- Cleaner separation
- Works with AJAX cart updates

**Cons**:
- Extra API call
- More complex
- Requires server + client changes

## Recommended Fix: Option 1

**Why**: Simplest, most effective, no UX changes needed

**Implementation**:
1. Modify `product_view()` in `apps/pantry/views.py`
2. Pass separate `all_products_json` and `filtered_products_by_category`
3. Update template to use `all_products_json` for cart
4. Test with search + cart interactions

**Expected Outcome**:
- ✅ Cart shows all items regardless of search
- ✅ Cart total is always correct  
- ✅ No user confusion
- ✅ Minimal code changes

## Testing

Run search bug tests:
```bash
npm test cart-search-bug.test.js
```

All 12 tests document the current buggy behavior and will verify the fix works.

## Next Steps

1. ✅ **IMPLEMENTED** - Option 1 fix applied
2. ✅ Modified `apps/pantry/views.py` - Pass separate product lists
3. ✅ Modified `apps/pantry/templates/food_orders/create_order.html` - Use allProducts for cart
4. ✅ All 78 cart tests passing
5. ☐ Manual testing in production environment

## Implementation Summary

**Files Changed:**

1. **apps/pantry/views.py**
   - Modified `group_products_by_category()` to accept `all_products_for_cart` parameter
   - Returns 3 values: `products_by_category`, `products_json`, `all_products_json`
   - Modified `product_view()` to pass both filtered and complete product lists
   - Template now receives both `products_json` (filtered) and `all_products_json` (complete)

2. **apps/pantry/templates/food_orders/create_order.html**
   - Added `allProducts` variable from `all_products_json`
   - Changed `renderCart()` to use `allProducts[productId]` instead of `products[productId]`
   - Cart now renders all items regardless of search filters

**How It Works:**

```javascript
// BEFORE (buggy):
const products = JSON.parse("{{ products_json|escapejs }}");  // Filtered by search
const product = products[productId];  // ← Fails if product not in search results

// AFTER (fixed):
const products = JSON.parse("{{ products_json|escapejs }}");      // Filtered for display
const allProducts = JSON.parse("{{ all_products_json|escapejs }}"); // Complete list
const product = allProducts[productId];  // ✓ Always finds product
```

**Testing:**

All 78 existing cart tests continue to pass. The fix maintains backward compatibility while solving the search bug.
