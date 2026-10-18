"""
Tests for core.middleware.LegacyParticipantRedirectMiddleware: the old
Django participant pages send people to the React app at /cart/.
"""
import pytest
from django.test import Client


@pytest.fixture
def redirects_on(settings):
    settings.LEGACY_PARTICIPANT_REDIRECTS = True
    settings.PARTICIPANT_APP_PATH = '/cart/'


@pytest.mark.django_db
@pytest.mark.parametrize('old, new', [
    ('/login/', '/cart/login'),
    ('/dashboard/', '/cart/products'),
    ('/create-order/', '/cart/products'),
    ('/review-order/', '/cart/checkout'),
    ('/order-success/', '/cart/orders'),
    ('/order/abc123XYZ/', '/cart/orders'),
    ('/account/update/', '/cart/account'),
    ('/accounts/password_change/', '/cart/account'),
])
def test_old_pages_redirect_to_react(redirects_on, old, new):
    response = Client().get(old)

    assert response.status_code == 302  # temporary, so turning it off works at once
    assert response.url == new


@pytest.mark.django_db
def test_query_string_is_dropped(redirects_on):
    response = Client().get('/login/?next=/dashboard/')

    assert response.url == '/cart/login'


@pytest.mark.django_db
def test_posts_are_not_redirected(redirects_on):
    # A form posted from an already-open old page still reaches Django
    response = Client().post('/review-order/')

    assert response.status_code == 302
    assert not response.url.startswith('/cart/')


@pytest.mark.django_db
@pytest.mark.parametrize('path', [
    '/',
    '/password_reset/',
    '/reset/done/',
    '/api/health/',
    '/admin/login/',
])
def test_other_pages_are_untouched(redirects_on, path):
    response = Client().get(path)

    assert not (response.status_code in (301, 302) and response.url.startswith('/cart/'))


@pytest.mark.django_db
def test_off_serves_the_django_page(settings):
    settings.LEGACY_PARTICIPANT_REDIRECTS = False

    response = Client().get('/login/')

    assert response.status_code == 200
