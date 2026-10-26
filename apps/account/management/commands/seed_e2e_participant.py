"""
Seed a deterministic participant fixture for the participant-frontend
Playwright e2e suite.

Creates (idempotently):
  - An active VoucherSetting, if none exists
  - A fixed Django User (username/password below)
  - A Participant linked to that user (gets 2 auto-applied grocery
    vouchers via the usual initialize_participant signal)
  - Products in a food category and in the "Hygiene" and "Go Fresh"
    categories (matched case-insensitively, the way validation matches
    them), each priced to put the cart in one balance situation:
      * far over every balance ($999.99), so a 'balance' error is certain
      * $5 over the hygiene balance or the Go Fresh cap, inside the food
        balance, so only that one rule fires
      * just over the food balance but inside the grace allowance
      * just under the food balance, so a small hygiene item pushes the
        combined food + hygiene total over it
      * cheap items that fit every balance
    The relative prices are worked out from the participant's balances
    and the grace amount as they stand now, so re-run this command after
    changing VoucherSetting, HygieneSettings, GoFreshSettings or
    ProgramSettings.

Also cancels the participant's open orders: a participant may only have
one pending order at a time, and the suite places a real order.

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

FOOD_CATEGORY_NAME = "E2E Test Category"
HYGIENE_CATEGORY_NAME = "Hygiene"
GO_FRESH_CATEGORY_NAME = "Go Fresh"

OVER_BUDGET_PRICE = Decimal("999.99")
SMALL_ITEM_PRICE = Decimal("5.00")
OVER_CAP_MARGIN = Decimal("5.00")

OVER_BUDGET_PRODUCT_NAME = "E2E Over-Budget Test Item"
GRACE_PRODUCT_NAME = "E2E Grace Test Item"
NEAR_BUDGET_PRODUCT_NAME = "E2E Near-Budget Food Item"
SMALL_FOOD_PRODUCT_NAME = "E2E Small Food Item"
OVER_HYGIENE_PRODUCT_NAME = "E2E Over-Budget Hygiene Item"
SMALL_HYGIENE_PRODUCT_NAME = "E2E Small Hygiene Item"
OVER_GO_FRESH_PRODUCT_NAME = "E2E Over-Budget Go Fresh Item"
SMALL_GO_FRESH_PRODUCT_NAME = "E2E Small Go Fresh Item"

OPEN_ORDER_STATUSES = ("pending", "confirmed", "packing")


class Command(BaseCommand):
    help = (
        "Seed a deterministic participant + balance-scenario products for the "
        "participant-frontend e2e suite"
    )

    def handle(self, *args, **options):
        from apps.account.models import Participant
        from apps.orders.models import Order
        from apps.voucher.models import VoucherSetting
        from core.models import ProgramSettings

        with transaction.atomic():
            if not VoucherSetting.objects.filter(active=True).exists():
                # infant_modifier has no model default, so a fresh DB needs it
                # spelled out (same value as the test VoucherSettingFactory).
                VoucherSetting.objects.create(active=True, infant_modifier=Decimal("0.50"))

            user, _ = User.objects.get_or_create(
                username=E2E_USERNAME,
                defaults={"email": E2E_EMAIL},
            )
            user.set_password(E2E_PASSWORD)
            user.save(update_fields=["password"])

            participant, _ = Participant.objects.get_or_create(
                user=user,
                defaults={
                    "name": "E2E Participant",
                    "email": E2E_EMAIL,
                    "adults": 1,
                },
            )
            account = participant.accountbalance

            # Cancel the way the staff cancel endpoint does: Order.save()
            # restores vouchers and stock for anything already confirmed
            cancelled_count = 0
            for order in Order.objects.filter(account=account, status__in=OPEN_ORDER_STATUSES):
                order.status = "cancelled"
                order.save(update_fields=["status", "updated_at"])
                cancelled_count += 1

            available_balance = account.available_balance
            grace_settings = ProgramSettings.get_settings()
            inside_grace = (grace_settings.grace_amount / 2).quantize(Decimal("0.01"))

            food = self._category(FOOD_CATEGORY_NAME)
            hygiene = self._category(HYGIENE_CATEGORY_NAME)
            go_fresh = self._category(GO_FRESH_CATEGORY_NAME)

            products = [
                self._product(OVER_BUDGET_PRODUCT_NAME, food, OVER_BUDGET_PRICE),
                self._product(GRACE_PRODUCT_NAME, food, available_balance + inside_grace),
                self._product(NEAR_BUDGET_PRODUCT_NAME, food, available_balance - Decimal("1.00")),
                self._product(SMALL_FOOD_PRODUCT_NAME, food, SMALL_ITEM_PRICE),
                self._product(OVER_HYGIENE_PRODUCT_NAME, hygiene, account.hygiene_balance + OVER_CAP_MARGIN),
                self._product(SMALL_HYGIENE_PRODUCT_NAME, hygiene, SMALL_ITEM_PRICE),
                self._product(OVER_GO_FRESH_PRODUCT_NAME, go_fresh, account.go_fresh_balance + OVER_CAP_MARGIN),
                self._product(SMALL_GO_FRESH_PRODUCT_NAME, go_fresh, SMALL_ITEM_PRICE),
            ]

        self.stdout.write(self.style.SUCCESS(
            f"E2E participant ready — username={E2E_USERNAME} password={E2E_PASSWORD}"
        ))
        self.stdout.write(
            f"Balances: food ${available_balance}, hygiene ${account.hygiene_balance}, "
            f"Go Fresh ${account.go_fresh_balance}; grace "
            f"{'$' + str(grace_settings.grace_amount) if grace_settings.grace_enabled else 'off'}"
        )
        if cancelled_count:
            self.stdout.write(f"Cancelled {cancelled_count} open order(s) from earlier runs")
        for product in products:
            self.stdout.write(f"  {product.name} ({product.category.name}): ${product.price}")

    @staticmethod
    def _category(name):
        from apps.pantry.models import Category

        category = Category.objects.filter(name__iexact=name).first()
        return category or Category.objects.create(name=name)

    @staticmethod
    def _product(name, category, price):
        from apps.pantry.models import Product

        product, _ = Product.objects.update_or_create(
            name=name,
            defaults={
                "category": category,
                "price": price,
                "description": "Seeded e2e fixture, priced for one balance scenario.",
                "quantity_in_stock": 100,
                "active": True,
            },
        )
        return product
