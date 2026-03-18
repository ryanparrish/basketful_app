"""
Management command to seed test data for combined order testing.

Creates:
  - 1 VoucherSetting (active)
  - 2 Programs (Monday Morning, Tuesday Afternoon)
  - 6 Participants (3 per program)
  - AccountBalance + 2 applied Vouchers per participant
  - 2 Categories + 6 Products (produce, dairy, protein)
  - 1 confirmed Order per participant dated today
  - 2 OrderItems per order (random products)

Usage:
    python manage.py seed_test_orders
    python manage.py seed_test_orders --clear   # wipe seed data first
"""

import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

User = get_user_model()


class Command(BaseCommand):
    help = "Seed test programs, participants, vouchers and confirmed orders for combined order testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously seeded data before re-seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()

        with transaction.atomic():
            self._seed()

        self.stdout.write(self.style.SUCCESS("\n✅  Seed complete — ready to test combined orders!\n"))
        self.stdout.write("   Use date range: today in the wizard\n")
        self.stdout.write("   Programs: 'Monday Morning' and 'Tuesday Afternoon'\n")

    # ------------------------------------------------------------------
    def _clear(self):
        from apps.orders.models import Order, OrderItem
        from apps.account.models import Participant, AccountBalance
        from apps.voucher.models import Voucher, VoucherSetting
        from apps.lifeskills.models import Program
        from apps.pantry.models import Product, Category

        self.stdout.write("Clearing previous seed data…")
        seed_programs = ["Monday Morning", "Tuesday Afternoon"]
        seed_categories = ["Produce", "Dairy", "Protein"]

        Order.objects.filter(account__participant__program__name__in=seed_programs).delete()
        AccountBalance.objects.filter(participant__program__name__in=seed_programs).delete()
        Participant.objects.filter(program__name__in=seed_programs).delete()
        Program.objects.filter(name__in=seed_programs).delete()
        Product.objects.filter(category__name__in=seed_categories).delete()
        Category.objects.filter(name__in=seed_categories).delete()
        self.stdout.write(self.style.WARNING("  Cleared.\n"))

    # ------------------------------------------------------------------
    def _seed(self):
        from apps.orders.models import Order, OrderItem
        from apps.account.models import Participant, AccountBalance
        from apps.voucher.models import Voucher, VoucherSetting
        from apps.lifeskills.models import Program
        from apps.pantry.models import Product, Category

        # ── VoucherSetting ──────────────────────────────────────────────
        # Use the existing active one or create a new one
        setting = VoucherSetting.objects.filter(active=True).first()
        if not setting:
            setting = VoucherSetting.objects.create(
                active=True,
                adult_amount=Decimal("50.00"),
                child_amount=Decimal("25.00"),
                infant_modifier=Decimal("10.00"),
            )
        self.stdout.write(f"  VoucherSetting: ${setting.adult_amount}/adult")

        # ── Categories & Products ───────────────────────────────────────
        produce, _ = Category.objects.get_or_create(name="Produce")
        dairy, _ = Category.objects.get_or_create(name="Dairy")
        protein, _ = Category.objects.get_or_create(name="Protein")

        products_data = [
            (produce, "Apples (bag)", "2.50"),
            (produce, "Baby Carrots", "1.99"),
            (dairy, "Whole Milk (gallon)", "4.29"),
            (dairy, "Eggs (dozen)", "3.49"),
            (protein, "Chicken Thighs (lb)", "5.99"),
            (protein, "Canned Tuna (seed)", "1.79"),
        ]
        products = []
        for cat, name, price in products_data:
            p, _ = Product.objects.get_or_create(
                name=name,
                category=cat,
                defaults=dict(
                    price=Decimal(price),
                    active=True,
                    quantity_in_stock=50,
                    description="",
                ),
            )
            products.append(p)
        self.stdout.write(f"  Products: {len(products)} created/found")

        # ── Programs ────────────────────────────────────────────────────
        program_data = [
            dict(name="Monday Morning", MeetingDay="monday",
                 meeting_time="09:00", meeting_address="123 Main St, Springfield"),
            dict(name="Tuesday Afternoon", MeetingDay="tuesday",
                 meeting_time="14:00", meeting_address="456 Oak Ave, Springfield"),
        ]
        programs = []
        for pd in program_data:
            prog, _ = Program.objects.get_or_create(name=pd["name"], defaults=pd)
            programs.append(prog)
            self.stdout.write(f"  Program: {prog.name}")

        # ── Participants + Accounts + Vouchers + Orders ─────────────────
        participant_names = [
            ("Alice Johnson", "alice@test.com", 2, 1),
            ("Bob Martinez", "bob@test.com", 1, 0),
            ("Carol Smith", "carol@test.com", 2, 2),
            ("David Lee", "david@test.com", 3, 0),
            ("Eva Chen", "eva@test.com", 2, 1),
            ("Frank Davis", "frank@test.com", 1, 1),
        ]

        today = timezone.now()

        for idx, (name, email, adults, children) in enumerate(participant_names):
            program = programs[idx % 2]  # alternate programs

            # Participant
            participant, _ = Participant.objects.get_or_create(
                email=email,
                defaults=dict(
                    name=name,
                    program=program,
                    adults=adults,
                    children=children,
                    active=True,
                ),
            )

            # AccountBalance
            account, _ = AccountBalance.objects.get_or_create(
                participant=participant,
                defaults=dict(base_balance=Decimal("100.00")),
            )

            # 2 applied grocery vouchers
            for _ in range(2):
                v = Voucher(
                    account=account,
                    voucher_type="grocery",
                    active=True,
                    notes="seed",
                )
                v.save()
                # bypass state validation — set directly
                Voucher.objects.filter(pk=v.pk).update(state="applied")

            # Confirmed Order
            order = Order(
                account=account,
                status="confirmed",
                paid=False,
            )
            order._ensure_order_number()
            order.save()

            # 2 OrderItems — pick random products
            picked = random.sample(products, 2)
            for product in picked:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=random.randint(1, 3),
                    price=product.price,
                    price_at_order=product.price,
                )

            self.stdout.write(
                f"  ✓ {name} → {program.name} | "
                f"Order #{order.order_number} | "
                f"{adults}A/{children}C"
            )
