"""
Tests for staff-entered catalog translations (django-modeltranslation).

Covers:
- Spanish participants see name_es via the plain `name` API field
- Blank translations fall back to English
- Staff serializer round-trips both language columns
"""
import pytest
from django.utils import translation
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.orders.tests.factories import (
    CategoryFactory,
    ParticipantFactory,
    ProductFactory,
    UserFactory,
    VoucherSettingFactory,
)


@pytest.fixture(autouse=True)
def voucher_setting():
    return VoucherSettingFactory(active=True)


@pytest.fixture(autouse=True)
def reset_language():
    yield
    translation.activate('en')


def jwt_client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


@pytest.mark.django_db
class TestCatalogTranslationFallback:

    def test_active_language_resolves_translated_name(self):
        product = ProductFactory(name='Rice')
        product.name_es = 'Arroz'
        product.save()

        with translation.override('es'):
            product.refresh_from_db()
            assert product.name == 'Arroz'

        with translation.override('en'):
            product.refresh_from_db()
            assert product.name == 'Rice'

    def test_blank_translation_falls_back_to_english(self):
        product = ProductFactory(name='Beans')

        with translation.override('es'):
            product.refresh_from_db()
            assert product.name == 'Beans'


@pytest.mark.django_db
class TestCatalogTranslationAPI:

    def test_spanish_participant_sees_spanish_product_name(self):
        participant = ParticipantFactory(preferred_language='es')
        product = ProductFactory(name='Milk', active=True)
        product.name_es = 'Leche'
        product.save()

        client = jwt_client_for(participant.user)
        response = client.get('/api/v1/products/')

        assert response.status_code == 200
        results = response.data.get('results', response.data)
        names = [p['name'] for p in results]
        assert 'Leche' in names
        assert 'Milk' not in names

    def test_english_participant_sees_english_product_name(self):
        participant = ParticipantFactory(preferred_language='en')
        product = ProductFactory(name='Milk', active=True)
        product.name_es = 'Leche'
        product.save()

        client = jwt_client_for(participant.user)
        response = client.get('/api/v1/products/')

        assert response.status_code == 200
        results = response.data.get('results', response.data)
        names = [p['name'] for p in results]
        assert 'Milk' in names

    def test_staff_serializer_round_trips_language_columns(self):
        staff_user = UserFactory(is_staff=True)
        category = CategoryFactory()
        client = jwt_client_for(staff_user)

        create_response = client.post(
            '/api/v1/products/',
            {
                'name': 'Bread',
                'name_es': 'Pan',
                'price': '2.50',
                'category': category.id,
                'quantity_in_stock': 10,
            },
            format='json',
        )
        assert create_response.status_code == 201, create_response.data
        assert create_response.data['name_en'] == 'Bread'
        assert create_response.data['name_es'] == 'Pan'
        # Staff requests are pinned to English, so the plain field reads English
        assert create_response.data['name'] == 'Bread'
