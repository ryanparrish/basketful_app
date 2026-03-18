"""
Management command to seed historical orders spread across past months.
Used to populate the Product Consumption Trends dashboard chart.

Usage:
    python manage.py seed_historical_orders
    python manage.py seed_historical_orders --months 6 --orders-per-week 10
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = "Seed historical orders across past months for dashboard trend analysis"

    def add_arguments(self, parser):
        parser.add_argument(
            '--months', type=int, default=6,
            help='Number of past months to seed (default: 6)',
        )
        parser.add_argument(
            '--orders-per-week', type=int, default=10,
            help='Approximate orders per week (default: 10)',
        )

    def handle(self, *args, **options):
        from apps.account.models import AccountBalance
        from apps.pantry.models import Product
        from apps.orders.models import Order, OrderItem

        months = options['months']
        orders_per_week = options['orders_per_week']

        accounts = list(AccountBalance.objects.select_related('participant').all())
        products = list(Product.objects.filter(active=True).all())

        if not accounts:
            self.stdout.write(self.style.ERROR("No accounts found. Run seed_db first."))
            return
        if not products:
            self.stdout.write(self.style.ERROR("No products found. Run seed_db first."))
            return

        self.stdout.write(
            f"Seeding ~{orders_per_week} orders/week across {months} months "
            f"({len(accounts)} accounts, {len(products)} products)..."
        )

        today = timezone.now()
        start = today - timedelta(days=months * 30)
        statuses = ['confirmed', 'confirmed', 'completed', 'completed', 'packing']

        total_orders = 0
        total_items = 0

        with transaction.atomic():
            current = start
            while current < today:
                num_orders = random.randint(
                    max(1, orders_per_week - 2),
                    orders_per_week + 2,
                )
                for _ in range(num_orders):
                    account = random.choice(accounts)
                    order_date = current + timedelta(
                        days=random.randint(0, 6),
                        hours=random.randint(8, 18),
                        minutes=random.randint(0, 59),
                    )
                    if order_date > today:
                        order_date = today - timedelta(minutes=random.randint(1, 60))

                    order = Order(
                        account=account,
                        status=random.choice(statuses),
                        paid=random.random() > 0.3,
                    )
                    order._ensure_order_number()
                    order.save()
                    # Override auto_now_add order_date with historical date
                    Order.objects.filter(pk=order.pk).update(order_date=order_date)

                    picked = random.sample(products, min(random.randint(2, 5), len(products)))
                    for product in picked:
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=random.randint(1, 4),
                            price=product.price,
                            price_at_order=product.price,
                        )
                        total_items += 1
                    total_orders += 1

                current += timedelta(days=7)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Seeded {total_orders} historical orders with {total_items} items "
            f"across {months} months."
        ))
