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
  6. Entry and history are staff-only (admin); non-staff are turned away.
  7. A product's history lists its movements (who, when, kind, quantity,
     note), newest first.
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client
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


class TestAdminEntryAndPermissions:

    def test_staff_can_create_movement_via_admin(self, staff_user):
        product = ProductFactory(name='Canned Soup', quantity_in_stock=16)
        client = Client()
        client.force_login(staff_user)
        response = client.post(
            reverse('admin:pantry_stockmovement_add'),
            {
                'product': str(product.pk),
                'quantity_change': '24',
                'kind': StockMovement.Kind.RECEIVED,
                'note': 'Morning delivery',
            },
        )
        assert response.status_code == 302
        product.refresh_from_db()
        assert product.quantity_in_stock == 40
        movement = StockMovement.objects.get(product=product)
        assert movement.entered_by == staff_user
        assert movement.note == 'Morning delivery'

    def test_non_staff_cannot_open_entry_form(self, plain_user):
        client = Client()
        client.force_login(plain_user)
        response = client.get(reverse('admin:pantry_stockmovement_add'))
        assert response.status_code in (302, 403)

    def test_anonymous_cannot_open_entry_form(self):
        client = Client()
        response = client.get(reverse('admin:pantry_stockmovement_add'))
        assert response.status_code == 302

    def test_admin_refuses_delete(self, staff_user):
        product = ProductFactory(quantity_in_stock=10)
        movement = StockMovement.objects.create(
            product=product, quantity_change=5,
            kind=StockMovement.Kind.RECEIVED, entered_by=staff_user,
        )
        client = Client()
        client.force_login(staff_user)
        response = client.post(
            reverse('admin:pantry_stockmovement_delete', args=[movement.pk]),
            {'post': 'yes'},
        )
        assert response.status_code in (302, 403, 404)
        assert StockMovement.objects.filter(pk=movement.pk).exists()


class TestProductHistoryView:

    def test_history_lists_movements_newest_first(
        self, staff_user
    ):
        product = ProductFactory(name='Canned Soup', quantity_in_stock=16)
        StockMovement.objects.create(
            product=product, quantity_change=24,
            kind=StockMovement.Kind.RECEIVED,
            note='Morning delivery', entered_by=staff_user,
        )
        StockMovement.objects.create(
            product=product, quantity_change=-2,
            kind=StockMovement.Kind.CORRECTION,
            note='Count was off', entered_by=staff_user,
        )
        other = ProductFactory(name='Other Product')
        StockMovement.objects.create(
            product=other, quantity_change=9,
            kind=StockMovement.Kind.DONATION, note='Not this product',
        )

        client = Client()
        client.force_login(staff_user)
        response = client.get(
            reverse('admin:product_stock_history', args=[product.pk])
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Canned Soup' in content
        # Current count reflects both movements: 16 + 24 - 2.
        assert '38' in content
        assert 'Morning delivery' in content
        assert 'Count was off' in content
        assert 'pantry-staff' in content
        # The other product's movement is not listed here.
        assert 'Not this product' not in content
        # Newest movement (the correction) is listed before the receiving.
        assert content.index('Count was off') < content.index(
            'Morning delivery'
        )

    def test_history_requires_staff(self, plain_user):
        product = ProductFactory()
        client = Client()
        client.force_login(plain_user)
        response = client.get(
            reverse('admin:product_stock_history', args=[product.pk])
        )
        assert response.status_code in (302, 403)
