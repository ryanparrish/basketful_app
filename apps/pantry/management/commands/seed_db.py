# food_orders/management/commands/seed_food_orders.py

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.pantry.models import (
    Category, Product
)

from apps.pantry.tests.factories import (
    ParticipantFactory, VoucherFactory, OrderFactory, OrderItemFactory
)

# -------------------------------
# Product Lists
# -------------------------------
PANTRY_CATEGORIES = {
    "Grains & Pasta": [
        "White Rice", "Brown Rice", "Quinoa", "Spaghetti", "Macaroni",
        "Couscous", "Oats", "Lentils", "Barley", "Pasta Shells"
    ],
    "Baking Supplies": [
        "All-Purpose Flour", "Whole Wheat Flour", "Sugar", "Brown Sugar",
        "Baking Powder", "Baking Soda", "Yeast", "Cornstarch", "Vanilla Extract"
    ],
    "Canned Goods": [
        "Black Beans", "Chickpeas", "Kidney Beans", "Canned Corn",
        "Canned Tuna", "Tomato Sauce", "Coconut Milk", "Canned Tomatoes"
    ],
    "Snacks": [
        "Crackers", "Granola Bars", "Potato Chips", "Popcorn",
        "Trail Mix", "Pretzels", "Nuts", "Rice Cakes"
    ],
    "Condiments & Sauces": [
        "Ketchup", "Mustard", "Mayonnaise", "Soy Sauce",
        "Hot Sauce", "BBQ Sauce", "Vinegar", "Worcestershire Sauce"
    ],
    "Oils & Vinegars": [
        "Olive Oil", "Vegetable Oil", "Canola Oil", "Balsamic Vinegar",
        "Apple Cider Vinegar", "Sesame Oil", "Sunflower Oil"
    ],
    "Breakfast Foods": [
        "Cereal", "Pancake Mix", "Oatmeal", "Instant Porridge",
        "Granola", "Muffin Mix", "Waffle Mix"
    ],
    "Beverages": [
        "Coffee", "Tea", "Orange Juice", "Apple Juice",
        "Hot Chocolate", "Soda", "Lemonade", "Herbal Tea"
    ],
    "Spices & Herbs": [
        "Salt", "Black Pepper", "Paprika", "Basil", "Oregano",
        "Cumin", "Chili Powder", "Thyme", "Rosemary", "Cinnamon"
    ],
    "Frozen Foods": [
        "Frozen Peas", "Frozen Corn", "Frozen Berries", "Frozen Pizza",
        "Frozen Chicken Nuggets", "Frozen Vegetables", "Frozen Fish Fillets"
    ],
}

MEAT_CATEGORIES = {
    "Fresh Beef": [
        "Ground Beef", "Ribeye Steak", "Sirloin Steak", "Chuck Roast",
        "Beef Brisket", "Beef Short Ribs"
    ],
    "Fresh Poultry": [
        "Chicken Breast", "Whole Chicken", "Chicken Thighs", "Turkey Breast",
        "Chicken Drumsticks", "Turkey Legs"
    ],
    "Fresh Pork": [
        "Pork Chops", "Bacon", "Pork Tenderloin", "Ham",
        "Pork Sausage Links", "Ground Pork"
    ],
    "Processed Meats": [
        "Hot Dogs", "Deli Ham", "Pepperoni", "Salami",
        "Beef Jerky", "Bologna"
    ],
    "Seafood": [
        "Salmon Fillet", "Shrimp", "Tilapia", "Canned Tuna",
        "Cod Fillet", "Crab Meat", "Scallops"
    ],
    "Plant-Based Proteins": [
        "Tofu", "Tempeh", "Chickpea Burgers", "Seitan",
        "Lentils", "Black Beans", "Edamame"
    ]
}

# -------------------------------
# Management Command
# -------------------------------
class Command(BaseCommand):
    help = "Seed the database with products, categories, participants, vouchers, and orders"

    def handle(self, *args, **options):
        self.stdout.write("Seeding categories and products...")

        # Create categories and products
        for cat_name, product_list in {**PANTRY_CATEGORIES, **MEAT_CATEGORIES}.items():
            category, _ = Category.objects.get_or_create(name=cat_name)
            for prod_name in product_list:
                Product.objects.get_or_create(
                    name=prod_name,
                    category=category,
                    defaults={"price": Decimal(random.randint(2, 50)), "quantity_in_stock": random.randint(5, 50)}
                )
        self.stdout.write(self.style.SUCCESS("Categories and products created."))

        # Create participants
        self.stdout.write("Seeding participants...")
        participants = [ParticipantFactory() for _ in range(20)]
        self.stdout.write(
            self.style.SUCCESS(
                f"{len(participants)} participants created."
            )
        )

        # Create vouchers
        self.stdout.write("Seeding vouchers...")
        vouchers = []
        for participant in participants:
            # Set the account balance
            account = participant.accountbalance
            account.base_balance = random.randint(50, 200)  # noqa: S311
            account.save()
            
            # Create voucher linked to the account
            voucher = VoucherFactory(account=account)
            vouchers.append(voucher)
        self.stdout.write(
            self.style.SUCCESS(f"{len(vouchers)} vouchers created.")
        )

        # Create orders and order items
        self.stdout.write("Seeding orders...")
        products = list(Product.objects.all())
        orders = []
        for participant in participants:
            for _ in range(random.randint(1, 3)):  # 1–3 orders per participant
                order = OrderFactory(account=participant.accountbalance)
                num_items = random.randint(1, 5)
                for _ in range(num_items):
                    product = random.choice(products)
                    OrderItemFactory(order=order, product=product, quantity=random.randint(1, 3))
                orders.append(order)
        self.stdout.write(self.style.SUCCESS(f"{len(orders)} orders created."))

        self.stdout.write(self.style.SUCCESS("Seeding complete!"))
