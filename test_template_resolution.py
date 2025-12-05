#!/usr/bin/env python
"""Test which template file Django actually loads."""
import os
import sys
import django

# Add project to path
sys.path.insert(0, '/Users/ryanparrish/lyn_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Setup Django
django.setup()

from django.template.loader import get_template
from django.conf import settings

print("=" * 70)
print("DJANGO TEMPLATE RESOLUTION TEST")
print("=" * 70)

# Get the template
try:
    template = get_template('pantry/create_order.html')
    print(f"\n✅ Template found!")
    print(f"📁 Template file: {template.origin.name}")
    print(f"📂 Template directory: {os.path.dirname(template.origin.name)}")
    
    # Read the template content to check for allProducts
    with open(template.origin.name, 'r') as f:
        content = f.read()
        
    print(f"\n🔍 Checking template content...")
    
    has_all_products_json = 'all_products_json' in content
    has_allProducts_var = 'const allProducts' in content
    has_allProducts_usage = 'allProducts[productId]' in content
    
    print(f"   - Has 'all_products_json' in template: {'✅ YES' if has_all_products_json else '❌ NO'}")
    print(f"   - Has 'const allProducts' variable: {'✅ YES' if has_allProducts_var else '❌ NO'}")
    print(f"   - Uses 'allProducts[productId]': {'✅ YES' if has_allProducts_usage else '❌ NO'}")
    
    if has_all_products_json and has_allProducts_var and has_allProducts_usage:
        print(f"\n🎉 SUCCESS: Template has the fix applied!")
    else:
        print(f"\n❌ PROBLEM: Template is missing the fix!")
        print(f"\n💡 You need to edit: {template.origin.name}")
        
        if not has_all_products_json:
            print(f"   - Add {{ all_products_json }} to template context")
        if not has_allProducts_var:
            print(f"   - Add: const allProducts = JSON.parse(\"{{ all_products_json|escapejs }}\");")
        if not has_allProducts_usage:
            print(f"   - Change: products[productId] → allProducts[productId] in renderCart()")
    
    print("\n" + "=" * 70)
    print("TEMPLATE SEARCH PATHS (in order):")
    print("=" * 70)
    
    from django.template.utils import get_app_template_dirs
    
    # Show all template directories Django searches
    for i, template_dir in enumerate(get_app_template_dirs('templates'), 1):
        potential_path = os.path.join(template_dir, 'pantry', 'create_order.html')
        exists = os.path.exists(potential_path)
        print(f"{i}. {template_dir}")
        print(f"   → {potential_path}")
        print(f"   {'✅ EXISTS' if exists else '❌ DOES NOT EXIST'}")
        if exists:
            print(f"   {'⭐ THIS ONE IS USED' if potential_path == template.origin.name else '   (not used)'}")
        print()
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)
