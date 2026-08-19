"""
Seed a deterministic participant fixture for the participant-frontend
Playwright e2e suite.

Creates (idempotently):
  - An active VoucherSetting, if none exists
  - A fixed Django User (username/password below)
  - A Participant linked to that user (gets 2 auto-applied grocery
    vouchers via the usual initialize_participant signal)
  - A Category + one Product priced far above any participant's budget,
    so adding it to the cart deterministically triggers a 'balance'
    validation violation

Usage:
    python manage.py seed_e2e_participant
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

E2E_USERNAME = "e2e-participant"
E2E_PASSWORD = "e2e-password"
E2E_EMAIL = "e2e-participant@example.com"
OVER_BUDGET_PRODUCT_NAME = "E2E Over-Budget Test Item"
OVER_BUDGET_PRICE = Decimal("999.99")


class Command(BaseCommand):
    help = (
        "Seed a deterministic participant + over-budget product for the "
        "participant-frontend e2e suite"
    )

    def handle(self, *args, **options):
        from apps.account.models import Participant
        from apps.pantry.models import Category, Product
        from apps.voucher.models import VoucherSetting

        with transaction.atomic():
            if not VoucherSetting.objects.filter(active=True).exists():
                VoucherSetting.objects.create(active=True)

            user, _ = User.objects.get_or_create(
                username=E2E_USERNAME,
                defaults={"email": E2E_EMAIL},
            )
            user.set_password(E2E_PASSWORD)
            user.save(update_fields=["password"])

            Participant.objects.get_or_create(
                user=user,
                defaults={
                    "name": "E2E Participant",
                    "email": E2E_EMAIL,
                    "adults": 1,
                },
            )

            category, _ = Category.objects.get_or_create(name="E2E Test Category")
            product, _ = Product.objects.update_or_create(
                name=OVER_BUDGET_PRODUCT_NAME,
                defaults={
                    "category": category,
                    "price": OVER_BUDGET_PRICE,
                    "description": "Seeded fixture — deliberately priced above any participant's budget.",
                    "quantity_in_stock": 100,
                    "active": True,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"E2E participant ready — username={E2E_USERNAME} password={E2E_PASSWORD}"
        ))
        self.stdout.write(f"Over-budget product: '{product.name}' (${product.price})")
