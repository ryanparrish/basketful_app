"""
#129: GET /api/v1/orders/ (order list) must not load data the list never
shows. The list used to share the detail view's queryset, which prefetches
every item's product/category/subcategory and every order's validation logs
on each page. The list now computes its item totals in SQL instead.
"""
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.log.models import OrderValidationLog
from apps.orders.api.serializers import OrderListSerializer
from apps.orders.models import Order
from apps.orders.tests.factories import (
    OrderFactory,
    OrderItemFactory,
    ParticipantFactory,
    VoucherSettingFactory,
)

# Tables only the order detail view needs
DETAIL_ONLY_TABLES = (
    OrderValidationLog._meta.db_table,
    'food_orders_product',
    'food_orders_category',
    'food_orders_subcategory',
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


def create_completed_order(participant, item_specs):
    """Create a completed order with items given as (quantity, price_at_order, price)."""
    order = OrderFactory(account=participant.accountbalance, status='completed')
    for quantity, price_at_order, price in item_specs:
        item = OrderItemFactory(order=order, quantity=quantity)
        # Set prices directly: OrderItem.save() snapshots prices on create
        type(item).objects.filter(pk=item.pk).update(price_at_order=price_at_order, price=price)
    return order


def list_my_orders(participant):
    client = APIClient()
    client.force_authenticate(user=participant.user)
    with CaptureQueriesContext(connection) as captured:
        response = client.get('/api/v1/orders/?me=true&page_size=50')
    assert response.status_code == 200, response.data
    results = response.data.get('results', response.data)
    return {row['id']: row for row in results}, captured


@pytest.mark.django_db
class TestOrderListQueries:

    def test_list_does_not_load_detail_only_tables(self):
        participant = ParticipantFactory()
        for _ in range(3):
            create_completed_order(participant, [(2, Decimal('1.50'), Decimal('1.50'))])

        _, captured = list_my_orders(participant)

        detail_table_queries = [
            query['sql'] for query in captured.captured_queries
            if any(table in query['sql'] for table in DETAIL_ONLY_TABLES)
        ]
        assert detail_table_queries == []

    def test_query_count_does_not_grow_with_orders(self):
        few = ParticipantFactory()
        many = ParticipantFactory()
        for _ in range(2):
            create_completed_order(few, [(1, Decimal('2.00'), Decimal('2.00'))])
        for _ in range(12):
            create_completed_order(many, [(1, Decimal('2.00'), Decimal('2.00'))] * 3)

        _, few_queries = list_my_orders(few)
        _, many_queries = list_my_orders(many)

        assert len(many_queries) == len(few_queries)

    def test_list_reports_item_totals(self):
        participant = ParticipantFactory()
        order = create_completed_order(participant, [
            (2, Decimal('3.25'), Decimal('9.99')),  # snapshotted price wins
            (3, None, Decimal('1.10')),             # legacy row: falls back to price
        ])
        empty_order = create_completed_order(participant, [])

        rows, _ = list_my_orders(participant)

        assert rows[order.id]['item_count'] == 2
        assert rows[order.id]['total_quantity'] == 5
        assert Decimal(str(rows[order.id]['total_price'])) == Decimal('9.80')
        assert rows[empty_order.id]['item_count'] == 0
        assert rows[empty_order.id]['total_quantity'] == 0
        assert Decimal(str(rows[empty_order.id]['total_price'])) == Decimal('0')

    def test_serializer_still_works_on_a_plain_queryset(self):
        """Other callers (program orders, combined orders) pass un-annotated orders."""
        participant = ParticipantFactory()
        order = create_completed_order(participant, [
            (2, Decimal('3.25'), Decimal('9.99')),
            (3, None, Decimal('1.10')),
        ])

        row = OrderListSerializer(Order.objects.get(pk=order.pk)).data

        assert row['item_count'] == 2
        assert row['total_quantity'] == 5
        assert Decimal(str(row['total_price'])) == Decimal('9.80')
