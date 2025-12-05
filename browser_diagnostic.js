"""
SEARCH + CART BUG DIAGNOSTIC TOOL

Run this in your browser's developer console when on the order page.
Copy and paste the entire script below:
*/

console.log("=".repeat(70));
console.log("🔍 SEARCH + CART BUG DIAGNOSTIC");
console.log("=".repeat(70));

// Test 1: Check if allProducts exists
console.log("\n📋 Test 1: Check allProducts variable");
console.log("-".repeat(70));
if (typeof allProducts !== 'undefined') {
    console.log("✅ allProducts is defined");
    console.log("   Product count:", Object.keys(allProducts).length);
    console.log("   Sample:", Object.entries(allProducts).slice(0, 2));
} else {
    console.error("❌ FAIL: allProducts is NOT defined!");
    console.error("   This means the template is not passing all_products_json");
    console.error("   Fix: Edit core/templates/pantry/create_order.html");
    console.error("   Add: const allProducts = JSON.parse(\"{{ all_products_json|escapejs }}\");");
}

// Test 2: Check if products exists
console.log("\n📋 Test 2: Check products variable");
console.log("-".repeat(70));
if (typeof products !== 'undefined') {
    console.log("✅ products is defined");
    console.log("   Product count:", Object.keys(products).length);
} else {
    console.error("❌ products is NOT defined (this is unexpected)");
}

// Test 3: Check renderCart function
console.log("\n📋 Test 3: Check renderCart implementation");
console.log("-".repeat(70));
if (typeof renderCart === 'function') {
    const source = renderCart.toString();
    if (source.includes('allProducts[productId]')) {
        console.log("✅ renderCart uses allProducts[productId]");
    } else if (source.includes('products[productId]')) {
        console.error("❌ FAIL: renderCart uses products[productId] (WRONG!)");
        console.error("   Fix: Change 'const product = products[productId]'");
        console.error("        to 'const product = allProducts[productId]'");
    } else {
        console.warn("⚠️  Cannot determine which variable renderCart uses");
    }
} else {
    console.error("❌ renderCart function not found");
}

// Test 4: Live cart test
console.log("\n📋 Test 4: Cart Bug Simulation");
console.log("-".repeat(70));

if (typeof cart !== 'undefined' && typeof products !== 'undefined' && typeof allProducts !== 'undefined') {
    // Save original state
    const originalProducts = {...products};
    const originalCart = {...cart};
    
    console.log("🧪 Setting up test...");
    
    // Add some test items if cart is empty
    if (Object.keys(cart).length === 0 && Object.keys(products).length > 0) {
        const productIds = Object.keys(products).slice(0, 3);
        console.log("   Adding test items to cart:", productIds);
        productIds.forEach((id, idx) => {
            cart[id] = idx + 1;
        });
    }
    
    console.log("   Cart items:", Object.keys(cart).length);
    console.log("   Products available:", Object.keys(products).length);
    console.log("   All products:", Object.keys(allProducts).length);
    
    // Simulate search filter
    console.log("\n🔍 Simulating search filter (keeping only first product)...");
    const firstProductId = Object.keys(products)[0];
    if (firstProductId) {
        products = {[firstProductId]: products[firstProductId]};
        console.log("   Filtered products to:", Object.keys(products).length, "item(s)");
    }
    
    // Try to render cart
    console.log("\n🎨 Calling renderCart()...");
    try {
        renderCart();
        
        // Count visible cart items
        const cartItems = document.querySelectorAll('#mobile-cart-items .list-group-item:not(.fw-bold)');
        const visibleCount = cartItems.length;
        const expectedCount = Object.keys(cart).length;
        
        console.log("   Visible cart items:", visibleCount);
        console.log("   Expected cart items:", expectedCount);
        
        if (visibleCount === expectedCount) {
            console.log("✅ SUCCESS: All cart items are visible!");
        } else {
            console.error("❌ FAIL: Only", visibleCount, "of", expectedCount, "items visible");
            console.error("   This means the bug still exists!");
        }
    } catch (err) {
        console.error("❌ Error calling renderCart():", err);
    }
    
    // Restore
    console.log("\n🔄 Restoring original state...");
    products = originalProducts;
    cart = originalCart;
    renderCart();
    console.log("   Restored");
    
} else {
    console.warn("⚠️  Skipping cart test - missing required variables");
}

// Test 5: Template source check
console.log("\n📋 Test 5: Check page source");
console.log("-".repeat(70));
const pageSource = document.documentElement.outerHTML;
if (pageSource.includes('const allProducts = JSON.parse')) {
    console.log("✅ Page source contains 'const allProducts = JSON.parse'");
} else {
    console.error("❌ FAIL: Page source does NOT contain allProducts definition");
    console.error("   Your browser may be showing cached content");
    console.error("   Try: Hard refresh (Cmd+Shift+R or Ctrl+Shift+R)");
}

// Final Summary
console.log("\n" + "=".repeat(70));
console.log("📊 DIAGNOSTIC SUMMARY");
console.log("=".repeat(70));

const checks = [
    typeof allProducts !== 'undefined',
    typeof renderCart === 'function' && renderCart.toString().includes('allProducts[productId]'),
    pageSource.includes('const allProducts = JSON.parse')
];

const passedCount = checks.filter(c => c).length;
const totalCount = checks.length;

if (passedCount === totalCount) {
    console.log("🎉 ALL CHECKS PASSED! The fix is working!");
    console.log("   If you're still seeing issues:");
    console.log("   1. Make sure to do a search on the page");
    console.log("   2. Add items to cart BEFORE searching");
    console.log("   3. Check if items stay visible after search");
} else {
    console.error("❌", passedCount, "of", totalCount, "checks passed");
    console.error("\n   Action needed:");
    console.error("   1. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)");
    console.error("   2. Clear browser cache");
    console.error("   3. Restart Django server");
    console.error("   4. Try incognito/private browsing mode");
}

console.log("=".repeat(70));

/*
*/
