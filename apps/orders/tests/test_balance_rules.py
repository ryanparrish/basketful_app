"""
One table of cart situations, run through every place the balance rules
apply: the participant's live cart check (validate-cart), order creation
(OrderOrchestration.create_order) and Order.clean(). If the cart says a
participant can check out, the order must go through, and the other way
round. See apps/orders/utils/balance_rules.py.

Every participant here has a $100 food balance, a $34 hygiene balance
(ceil($100 / 3)) and a $10 Go Fresh budget (one-person household), with
the default $1.00 grace allowance.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.account.models import GoFreshSettings
from apps.log.models import GraceAllowanceLog
from apps.orders.models import Order, OrderItem
from apps.orders.tests.factories import (
    CategoryFactory,
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherFactory,
    VoucherSettingFactory,
)
from apps.orders.utils.order_utils import OrderOrchestration
from apps.orders.utils.order_validation import OrderItemData
from core.models import ProgramSettings

VALIDATE_CART_URL = '/api/v1/orders/validate-cart/'

FOOD = 'Pantry'
HYGIENE = 'Hygiene'
GO_FRESH = 'Go Fresh'

OK = 'ok'            # no balance overage at all
WARNING = 'warning'  # over, but grace lets the order through
ERROR = 'error'      # over, and the order is blocked

SCENARIOS = [
    # id, cart lines (category, price), grace on?, Go Fresh on?, outcome, message
    ('within every balance',
     [(FOOD, '50.00'), (HYGIENE, '20.00'), (GO_FRESH, '8.00')], True, True, OK, None),
    ('food over inside grace',
     [(FOOD, '100.50')], True, True, WARNING, 'This helps you practice staying within budget'),
    ('food over inside grace, grace off',
     [(FOOD, '100.50')], False, True, ERROR, 'Food balance exceeded by $0.50'),
    ('food over beyond grace',
     [(FOOD, '101.50')], True, True, ERROR, 'Food balance exceeded by $1.50'),
    ('food exactly at the balance',
     [(FOOD, '100.00')], False, True, OK, None),
    ('hygiene over beyond grace',
     [(HYGIENE, '40.00')], True, True, ERROR, 'Hygiene balance exceeded by $6.00'),
    ('hygiene over inside grace',
     [(HYGIENE, '34.50')], True, True, WARNING, 'This helps you practice staying within budget'),
    ('food and hygiene each fit, together over',
     [(FOOD, '90.00'), (HYGIENE, '20.00')], True, True, ERROR, 'Food balance exceeded by $10.00'),
    ('Go Fresh spends the food balance',
     [(FOOD, '95.00'), (GO_FRESH, '8.00')], True, True, ERROR, 'Food balance exceeded by $3.00'),
    ('Go Fresh over inside grace',
     [(GO_FRESH, '10.50')], True, True, WARNING, 'This helps you practice staying within budget'),
    ('Go Fresh over inside grace, grace off',
     [(GO_FRESH, '10.50')], False, True, ERROR, 'Go Fresh balance exceeded by $0.50'),
    ('Go Fresh over beyond grace',
     [(GO_FRESH, '12.00')], True, True, ERROR, 'Go Fresh balance exceeded by $2.00'),
    ('hygiene over inside grace, grace off',
     [(HYGIENE, '34.50')], False, True, ERROR, 'Hygiene balance exceeded by $0.50'),
    ('Go Fresh cap off',
     [(GO_FRESH, '20.00')], True, False, OK, None),
]


@pytest.fixture
def make_participant(db):
    def make():
        VoucherSettingFactory.create()
        user = UserFactory()
        participant = ParticipantFactory(user=user, adults=1, children=0)
        account = participant.accountbalance
        account.base_balance = Decimal('50.00')
        account.save()
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
        VoucherFactory(account=account, state='applied', voucher_type='grocery', multiplier=1)
        assert account.available_balance == Decimal('100.00')
        assert account.hygiene_balance == Decimal('34')
        return participant, account
    return make


def configure(grace_on, go_fresh_on):
    program_settings = ProgramSettings.get_settings()
    program_settings.grace_enabled = grace_on
    program_settings.grace_amount = Decimal('1.00')
    program_settings.save()
    go_fresh_settings = GoFreshSettings.get_settings()
    go_fresh_settings.enabled = go_fresh_on
    go_fresh_settings.save()


def make_products(lines):
    categories = {}
    products = []
    for category_name, price in lines:
        if category_name not in categories:
            categories[category_name] = CategoryFactory(name=category_name)
        products.append(ProductFactory(
            category=categories[category_name],
            price=Decimal(price),
            quantity_in_stock=50,
        ))
    return products


@pytest.mark.django_db
@pytest.mark.parametrize(
    'lines, grace_on, go_fresh_on, outcome, message',
    [scenario[1:] for scenario in SCENARIOS],
    ids=[scenario[0] for scenario in SCENARIOS],
)
class TestEveryPathAppliesTheSameBalanceRule:

    def test_cart_check(self, make_participant, lines, grace_on, go_fresh_on, outcome, message):
        configure(grace_on, go_fresh_on)
        participant, _account = make_participant()
        products = make_products(lines)

        client = APIClient()
        client.force_authenticate(user=participant.user)
        response = client.post(
            VALIDATE_CART_URL,
            {'items': [{'product_id': product.id, 'quantity': 1} for product in products]},
            format='json',
        )

        assert response.status_code == 200, response.data
        data = response.json()
        balance_violations = [v for v in data['violations'] if v['type'] == 'balance']
        if outcome == OK:
            assert data['valid'] is True
            assert balance_violations == []
        else:
            assert data['valid'] is (outcome == WARNING)
            assert [v['severity'] for v in balance_violations] == [outcome]
            assert balance_violations[0]['message'] == message

    def test_order_creation(self, make_participant, lines, grace_on, go_fresh_on, outcome, message):
        configure(grace_on, go_fresh_on)
        participant, account = make_participant()
        items = [OrderItemData(product=product, quantity=1) for product in make_products(lines)]

        def create():
            return OrderOrchestration().create_order(
                account=account, order_items_data=items, user=participant.user,
            )

        if outcome == ERROR:
            with pytest.raises(ValidationError) as exc_info:
                create()
            assert message in str(exc_info.value)
            assert not Order.objects.filter(account=account).exists()
            return

        order = create()
        assert order.status == 'pending'
        grace_logs = GraceAllowanceLog.objects.filter(order=order)
        if outcome == WARNING:
            assert grace_logs.count() == 1
            assert grace_logs.get().proceeded is True
        else:
            assert not grace_logs.exists()

    def test_order_clean(self, make_participant, lines, grace_on, go_fresh_on, outcome, message):
        configure(grace_on, go_fresh_on)
        _participant, account = make_participant()
        order = Order.objects.create(account=account, status='pending')
        for product in make_products(lines):
            OrderItem.objects.create(order=order, product=product, quantity=1, price=product.price)
        order.status = 'confirmed'

        if outcome == ERROR:
            with pytest.raises(ValidationError) as exc_info:
                order.clean()
            assert message in str(exc_info.value)
        else:
            order.clean()


@pytest.mark.django_db
def test_cart_check_names_an_open_order_instead_of_failing(make_participant):
    participant, account = make_participant()
    Order.objects.create(account=account, status='pending')
    product = make_products([(FOOD, '5.00')])[0]

    client = APIClient()
    client.force_authenticate(user=participant.user)
    response = client.post(
        VALIDATE_CART_URL,
        {'items': [{'product_id': product.id, 'quantity': 1}]},
        format='json',
    )

    assert response.status_code == 200, response.data
    data = response.json()
    assert data['valid'] is False
    assert [v['type'] for v in data['violations']] == ['active_order']
    assert data['violations'][0]['message'].startswith('You already have an active order.')


@pytest.mark.django_db
def test_rejected_order_tells_the_participant_why(make_participant, grace_off):
    participant, _account = make_participant()
    product = make_products([(FOOD, '100.50')])[0]

    client = APIClient()
    client.force_authenticate(user=participant.user)
    response = client.post(
        '/api/v1/orders/',
        {'items': [{'product': product.id, 'quantity': 1}]},
        format='json',
    )

    assert response.status_code == 400, response.data
    assert response.data['error'] == 'Food balance exceeded by $0.50'
