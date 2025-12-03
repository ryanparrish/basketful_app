"""
Debug script to check why Ground Beef, Lunch Meat, and Wipes are grouped together.
Run this in Django shell to see the product assignments.
"""

# Run this in Django shell:
# python manage.py shell

from apps.pantry.models import Product

products = ['Ground Beef', 'Lunch Meat', 'Wipes']

print("=" * 80)
print("PRODUCT CATEGORY/SUBCATEGORY ASSIGNMENTS")
print("=" * 80)

for name in products:
    product = Product.objects.filter(name__icontains=name).first()
    if product:
        print(f"\n{product.name}:")
        print(f"  ID: {product.id}")
        print(f"  Category: {product.category.name if product.category else 'None'} (ID: {product.category.id if product.category else 'N/A'})")
        print(f"  Subcategory: {product.subcategory.name if product.subcategory else 'None'} (ID: {product.subcategory.id if product.subcategory else 'N/A'})")
        
        # What will be used for grouping?
        obj = product.subcategory or product.category
        if obj:
            print(f"  → Grouped by: {obj.name} (ID: {obj.id})")
    else:
        print(f"\n{name}: NOT FOUND")

print("\n" + "=" * 80)
print("ISSUE DIAGNOSIS:")
print("=" * 80)

# Check if they share the same grouping ID
found_products = [Product.objects.filter(name__icontains=name).first() for name in products]
found_products = [p for p in found_products if p]

if len(found_products) >= 2:
    grouping_ids = set()
    for p in found_products:
        obj = p.subcategory or p.category
        if obj:
            grouping_ids.add(obj.id)
    
    if len(grouping_ids) == 1:
        print("❌ PROBLEM FOUND: All products share the same category/subcategory!")
        print(f"   Grouping ID: {list(grouping_ids)[0]}")
        print("\n   This is why they're counted together.")
        print("\n   SOLUTION: Update the products to use correct categories/subcategories:")
        
        for p in found_products:
            obj = p.subcategory or p.category
            print(f"   - {p.name} is in '{obj.name}' subcategory/category")
            if p.name in ['Ground Beef', 'Lunch Meat']:
                print(f"     → Should probably be in 'Meat' or 'Protein' category")
            elif 'Wipe' in p.name:
                print(f"     → Should probably be in 'Baby Care' or 'Wipes' subcategory")
    else:
        print(f"✅ Products are in {len(grouping_ids)} different categories/subcategories")
        print(f"   This should NOT cause them to be grouped together.")
        print("   Need to investigate the order items being validated.")

print("\n" + "=" * 80)
