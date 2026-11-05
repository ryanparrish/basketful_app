"""
validate-cart tells the participant UI *which* cart lines caused each
violation (product_ids) and which balance it was (budget), so the cart can
highlight the offending items instead of a generic "fix cart errors".
"""
from decimal import Decimal
from unittest.mock import PropertyMock, patch

import pytest
from rest_framework.test import APIClient

from apps.account.models import AccountBalance
from apps.orders.tests.factories import (
    CategoryFactory,
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherSettingFactory,
)
from apps.pantry.models import Product, ProductLimit
from core.models import ProgramSettings

VALIDATE_CART_URL = '/api/v1/orders/validate-cart/'


@pytest.fixture
def client_and_participant(db):
    VoucherSettingFactory.create()
    ProgramSettings.get_settings()
    user = UserFactory()
    participant = ParticipantFactory(user=user)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, participant


def _balances(food='40.00', hygiene='0.00', go_fresh='0.00'):
    """Pin the three balances so each test controls exactly which one overflows."""
    return [
        patch.object(AccountBalance, 'available_balance', new_callable=PropertyMock,
                     return_value=Decimal(food)),
        patch.object(AccountBalance, 'hygiene_balance', new_callable=PropertyMock,
                     return_value=Decimal(hygiene)),
        patch.object(AccountBalance, 'go_fresh_balance', new_callable=PropertyMock,
                     return_value=Decimal(go_fresh)),
    ]


def _validate(client, items):
    response = client.post(
        VALIDATE_CART_URL,
        {'items': [{'product_id': p.id, 'quantity': q} for p, q in items]},
        format='json',
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.django_db
def test_product_budget_follows_protected_category_names():
    assert ProductFactory(category=CategoryFactory(name='Hygiene')).budget == Product.BUDGET_HYGIENE
    assert ProductFactory(category=CategoryFactory(name='Go Fresh')).budget == Product.BUDGET_GO_FRESH
    assert ProductFactory(category=CategoryFactory(name='Pantry Food')).budget == Product.BUDGET_FOOD
    assert ProductFactory(category=None).budget == Product.BUDGET_FOOD


def test_hygiene_overage_names_only_the_hygiene_lines(client_and_participant):
    client, _ = client_and_participant
    foil = ProductFactory(category=CategoryFactory(name='Hygiene'), price=Decimal('3.50'))
    beans = ProductFactory(category=CategoryFactory(name='Pantry Food'), price=Decimal('1.50'))

    patches = _balances(hygiene='0.00')
    for p in patches:
        p.start()
    try:
        data = _validate(client, [(foil, 1), (beans, 2)])
    finally:
        for p in patches:
            p.stop()

    assert data['valid'] is False
    [violation] = [v for v in data['violations'] if v['type'] == 'balance']
    assert violation['budget'] == 'hygiene'
    assert violation['product_ids'] == [foil.id]


def test_food_overage_excludes_hygiene_and_go_fresh_lines(client_and_participant):
    client, _ = client_and_participant
    rice = ProductFactory(category=CategoryFactory(name='Pantry Food'), price=Decimal('30.00'))
    beans = ProductFactory(category=CategoryFactory(name='Frozen Meat'), price=Decimal('20.00'))
    soap = ProductFactory(category=CategoryFactory(name='Hygiene'), price=Decimal('2.00'))

    patches = _balances(food='40.00', hygiene='10.00')
    for p in patches:
        p.start()
    try:
        data = _validate(client, [(rice, 1), (beans, 1), (soap, 1)])
    finally:
        for p in patches:
            p.stop()

    [violation] = [v for v in data['violations'] if v['type'] == 'balance']
    assert violation['budget'] == 'food'
    assert violation['product_ids'] == sorted([rice.id, beans.id])


def test_category_limit_violation_names_the_products_in_that_category(client_and_participant):
    client, participant = client_and_participant
    meat = CategoryFactory(name='Frozen Meat')
    chicken = ProductFactory(category=meat, price=Decimal('0.00'))
    beef = ProductFactory(category=meat, price=Decimal('0.00'))
    corn = ProductFactory(category=CategoryFactory(name='Pantry Food'), price=Decimal('0.00'))
    ProductLimit.objects.create(name='Meat', category=meat, limit=1, limit_scope='per_order')

    patches = _balances()
    for p in patches:
        p.start()
    try:
        data = _validate(client, [(chicken, 1), (beef, 1), (corn, 1)])
    finally:
        for p in patches:
            p.stop()

    [violation] = [v for v in data['violations'] if v['type'] == 'limit']
    assert violation['product_ids'] == sorted([chicken.id, beef.id])
