"""
Tests for StockMovement — manual stock entry with a receiving history
(Issue #144).

Business rules verified:
  1. Creating a movement updates Product.quantity_in_stock in the same
     transaction (receiving raises it, removals lower it).
  2. A movement may not drive stock below zero.
  3. A zero-quantity movement is rejected.
  4. Receiving stock does NOT reactivate an inactive product —
     reactivation stays a deliberate staff action.
  5. Movements are immutable: editing or deleting one is refused; a
     mistake is fixed with a new correction movement.
  6. Entry and history are staff-only (API at /api/v1/stock-movements/,
     used by the React admin); non-staff are turned away.
  7. A product's history lists its movements (who, when, kind, quantity,
     note), newest first.
  8. The API has no update or delete; rule violations come back as 400
     field errors, not 500s.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from django.urls import reverse

from apps.account.tests.helpers import password_already_chosen
from apps.pantry.models import Product, StockMovement
from apps.pantry.tests.factories import ProductFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def staff_user(db):
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        user = password_already_chosen(User.objects.create_user(
            username='pantry-staff', password='testpass123', is_staff=True
        ))
    # A pantry team member: staff with stock-movement permissions
    # (deliberately not delete — movements cannot be deleted).
    permissions = Permission.objects.filter(
        content_type__app_label='pantry',
        codename__in=(
            'add_stockmovement', 'view_stockmovement', 'view_product',
        ),
    )
    user.user_permissions.add(*permissions)
    return user


@pytest.fixture
def plain_user(db):
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        return password_already_chosen(User.objects.create_user(
            username='plain', password='testpass123'
        ))


class TestMovementUpdatesStock:

    def test_receiving_raises_stock(self):
        """Acceptance: record 24 cans received, stock rises by 24."""
        product = ProductFactory(quantity_in_stock=16)
        StockMovement.objects.create(
            product=product, quantity_change=24,
            kind=StockMovement.Kind.RECEIVED, note='Morning delivery',
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 40

    def test_removal_lowers_stock(self):
        product = ProductFactory(quantity_in_stock=40)
        StockMovement.objects.create(
            product=product, quantity_change=-6,
            kind=StockMovement.Kind.SPOILAGE, note='Damaged cans',
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 34

    def test_movements_accumulate(self):
        product = ProductFactory(quantity_in_stock=10)
        StockMovement.objects.create(
            product=product, quantity_change=24,
            kind=StockMovement.Kind.RECEIVED,
        )
        StockMovement.objects.create(
            product=product, quantity_change=12,
            kind=StockMovement.Kind.DONATION, note='Church food drive',
        )
        StockMovement.objects.create(
            product=product, quantity_change=-2,
            kind=StockMovement.Kind.CORRECTION, note='Count was off by two',
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 44
        assert product.stock_movements.count() == 3


class TestBelowZeroRejected:

    def test_movement_below_zero_raises_and_changes_nothing(self):
        product = ProductFactory(quantity_in_stock=5)
        with pytest.raises(ValidationError):
            StockMovement.objects.create(
                product=product, quantity_change=-6,
                kind=StockMovement.Kind.SPOILAGE,
            )
        product.refresh_from_db()
        assert product.quantity_in_stock == 5
        assert StockMovement.objects.count() == 0

    def test_movement_to_exactly_zero_is_allowed(self):
        product = ProductFactory(quantity_in_stock=5)
        StockMovement.objects.create(
            product=product, quantity_change=-5,
            kind=StockMovement.Kind.SPOILAGE,
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 0

    def test_zero_change_rejected(self):
        product = ProductFactory(quantity_in_stock=5)
        with pytest.raises(ValidationError):
            StockMovement.objects.create(
                product=product, quantity_change=0,
                kind=StockMovement.Kind.CORRECTION,
            )
        assert StockMovement.objects.count() == 0


class TestNoAutoReactivation:

    def test_receiving_keeps_inactive_product_inactive(self):
        product = ProductFactory(quantity_in_stock=0, active=False)
        StockMovement.objects.create(
            product=product, quantity_change=24,
            kind=StockMovement.Kind.RECEIVED,
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 24
        assert product.active is False


class TestImmutability:

    def test_existing_movement_cannot_be_edited(self):
        product = ProductFactory(quantity_in_stock=10)
        movement = StockMovement.objects.create(
            product=product, quantity_change=5,
            kind=StockMovement.Kind.RECEIVED,
        )
        movement.quantity_change = 50
        with pytest.raises(ValidationError):
            movement.save()
        product.refresh_from_db()
        assert product.quantity_in_stock == 15

    def test_movement_cannot_be_deleted(self):
        product = ProductFactory(quantity_in_stock=10)
        movement = StockMovement.objects.create(
            product=product, quantity_change=5,
            kind=StockMovement.Kind.RECEIVED,
        )
        with pytest.raises(ValidationError):
            movement.delete()
        assert StockMovement.objects.filter(pk=movement.pk).exists()

    def test_correction_is_a_new_movement(self):
        product = ProductFactory(quantity_in_stock=10)
        StockMovement.objects.create(
            product=product, quantity_change=24,
            kind=StockMovement.Kind.RECEIVED, note='Typed 24, was 14',
        )
        StockMovement.objects.create(
            product=product, quantity_change=-10,
            kind=StockMovement.Kind.CORRECTION,
            note='Correcting the receiving entry above',
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 24
        assert product.stock_movements.count() == 2


# ---------------------------------------------------------------------------
# Review fixes
# ---------------------------------------------------------------------------

class TestKindSignRules:

    @pytest.mark.parametrize('kind', [
        StockMovement.Kind.RECEIVED, StockMovement.Kind.DONATION,
    ])
    def test_incoming_kinds_reject_negative(self, kind):
        product = ProductFactory(quantity_in_stock=50)
        with pytest.raises(ValidationError):
            StockMovement.objects.create(
                product=product, quantity_change=-5, kind=kind,
            )

    def test_spoilage_rejects_positive(self):
        product = ProductFactory(quantity_in_stock=5)
        with pytest.raises(ValidationError):
            StockMovement.objects.create(
                product=product, quantity_change=5,
                kind=StockMovement.Kind.SPOILAGE,
            )

    @pytest.mark.parametrize('change', [3, -3])
    def test_correction_allows_either_sign(self, change):
        product = ProductFactory(quantity_in_stock=10)
        StockMovement.objects.create(
            product=product, quantity_change=change,
            kind=StockMovement.Kind.CORRECTION,
        )
        product.refresh_from_db()
        assert product.quantity_in_stock == 10 + change


class TestHistoryIsProtected:

    def test_product_with_movements_cannot_be_deleted(self):
        from django.db.models import ProtectedError

        product = ProductFactory(quantity_in_stock=1)
        StockMovement.objects.create(
            product=product, quantity_change=4,
            kind=StockMovement.Kind.RECEIVED,
        )
        with pytest.raises(ProtectedError):
            product.delete()
        assert StockMovement.objects.filter(product=product).exists()


class TestStockOnlyChangesThroughMovements:

    def test_product_admin_stock_readonly_on_change(self, rf, staff_user):
        from django.contrib import admin as django_admin

        product = ProductFactory()
        model_admin = django_admin.site._registry[Product]
        request = rf.get('/')
        request.user = staff_user
        assert 'quantity_in_stock' in model_admin.get_readonly_fields(
            request, product
        )
        # A new product still takes its initial count on the add form.
        assert 'quantity_in_stock' not in model_admin.get_readonly_fields(
            request, None
        )

    def test_api_rejects_direct_stock_edit(self):
        from apps.pantry.api.serializers import ProductSerializer

        product = ProductFactory(quantity_in_stock=10)
        serializer = ProductSerializer(
            product, data={'quantity_in_stock': 99}, partial=True,
        )
        assert not serializer.is_valid()
        assert 'quantity_in_stock' in serializer.errors

    def test_api_allows_unchanged_stock_value(self):
        from apps.pantry.api.serializers import ProductSerializer

        product = ProductFactory(quantity_in_stock=10)
        serializer = ProductSerializer(
            product, data={'quantity_in_stock': 10}, partial=True,
        )
        assert serializer.is_valid(), serializer.errors


# ---------------------------------------------------------------------------
# API used by the React admin (/api/v1/stock-movements/)
# ---------------------------------------------------------------------------

URL = '/api/v1/stock-movements/'


def _api(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


class TestStockMovementApi:

    def test_staff_records_receiving(self, staff_user):
        product = ProductFactory(name='Canned Soup', quantity_in_stock=16)
        response = _api(staff_user).post(URL, {
            'product': product.pk, 'quantity_change': 24,
            'kind': 'received', 'note': 'Morning delivery',
        }, format='json')
        assert response.status_code == 201, response.data
        assert response.data['stock_after'] == 40
        assert response.data['entered_by'] == staff_user.pk
        assert response.data['product_name'] == 'Canned Soup'
        product.refresh_from_db()
        assert product.quantity_in_stock == 40

    def test_entered_by_cannot_be_spoofed(self, staff_user, plain_user):
        product = ProductFactory(quantity_in_stock=1)
        response = _api(staff_user).post(URL, {
            'product': product.pk, 'quantity_change': 2,
            'kind': 'donation', 'entered_by': plain_user.pk,
        }, format='json')
        assert response.status_code == 201
        assert StockMovement.objects.get().entered_by == staff_user

    def test_below_zero_is_a_400_field_error(self, staff_user):
        product = ProductFactory(name='Rice', quantity_in_stock=5)
        response = _api(staff_user).post(URL, {
            'product': product.pk, 'quantity_change': -6, 'kind': 'spoilage',
        }, format='json')
        assert response.status_code == 400
        assert 'below zero' in str(response.data['quantity_change'])
        product.refresh_from_db()
        assert product.quantity_in_stock == 5
        assert not StockMovement.objects.exists()

    def test_wrong_sign_is_a_400_field_error(self, staff_user):
        product = ProductFactory(quantity_in_stock=5)
        response = _api(staff_user).post(URL, {
            'product': product.pk, 'quantity_change': -3, 'kind': 'received',
        }, format='json')
        assert response.status_code == 400
        assert 'must be positive' in str(response.data['quantity_change'])

    def test_zero_is_a_400(self, staff_user):
        product = ProductFactory(quantity_in_stock=5)
        response = _api(staff_user).post(URL, {
            'product': product.pk, 'quantity_change': 0, 'kind': 'correction',
        }, format='json')
        assert response.status_code == 400

    def test_no_update_or_delete(self, staff_user):
        product = ProductFactory(quantity_in_stock=10)
        movement = StockMovement.objects.create(
            product=product, quantity_change=5, kind='received',
        )
        client = _api(staff_user)
        assert client.patch(f'{URL}{movement.pk}/', {'quantity_change': 50},
                            format='json').status_code == 405
        assert client.put(f'{URL}{movement.pk}/', {}, format='json').status_code == 405
        assert client.delete(f'{URL}{movement.pk}/').status_code == 405
        product.refresh_from_db()
        assert product.quantity_in_stock == 15
        assert StockMovement.objects.filter(pk=movement.pk).exists()

    def test_history_for_one_product_newest_first(self, staff_user):
        product = ProductFactory(quantity_in_stock=16)
        other = ProductFactory()
        StockMovement.objects.create(product=product, quantity_change=24,
                                     kind='received', note='Morning delivery',
                                     entered_by=staff_user)
        StockMovement.objects.create(product=product, quantity_change=-2,
                                     kind='correction', note='Count was off',
                                     entered_by=staff_user)
        StockMovement.objects.create(product=other, quantity_change=9,
                                     kind='donation', note='Not this product')
        response = _api(staff_user).get(URL, {'product': product.pk})
        assert response.status_code == 200
        notes = [row['note'] for row in response.data['results']]
        assert notes == ['Count was off', 'Morning delivery']
        assert response.data['results'][0]['entered_by_name'] == 'pantry-staff'
        assert response.data['results'][0]['kind_display'] == 'Correction'

    def test_non_staff_and_anonymous_refused(self, plain_user):
        assert _api(plain_user).get(URL).status_code == 403
        assert _api().get(URL).status_code in (401, 403)
        product = ProductFactory(quantity_in_stock=1)
        response = _api(plain_user).post(URL, {
            'product': product.pk, 'quantity_change': 5, 'kind': 'received',
        }, format='json')
        assert response.status_code == 403
        assert not StockMovement.objects.exists()
