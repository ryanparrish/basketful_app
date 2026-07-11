"""
Tests for the email variable registry and the upgraded preview endpoint.

Covers Stage 1 of the Email Design Studio work (Issue #83):
  1. Every seeded EmailType renders subject/html/text with its per-type
     sample context — no TemplateSyntaxError, no empty variable holes.
  2. The onboarding email leads with the username again and keeps the
     customer number as a secondary note (migration 0017).
  3. Preview endpoint: GET per language, POST draft rendering without
     saving, 400 naming the field on template syntax errors, staff-only.
  4. EmailTypeSerializer round-trips the _es translation columns and
     exposes the variable registry.
  5. EmailSettings URL overrides fall back to env settings and survive
     the singleton save() copy.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.log.models import EmailType
from apps.log.variables import (
    EMAIL_TYPE_VARIABLES,
    build_sample_context,
    get_variables,
)
from core.models import EmailSettings

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _email_types(seeded_email_types):
    """Migration-seeded EmailTypes, resilient to DB flushes (see conftest)."""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestVariableRegistry:

    def test_every_seeded_type_has_a_registry_entry(self):
        for email_type in EmailType.objects.all():
            assert email_type.name in EMAIL_TYPE_VARIABLES, (
                f"EmailType '{email_type.name}' has no entry in "
                "apps/log/variables.py EMAIL_TYPE_VARIABLES — add one so the "
                "studio's variable picker and preview know its context."
            )

    def test_every_seeded_template_renders_with_sample_context(self):
        for email_type in EmailType.objects.all():
            context = email_type.get_sample_context_for_type()
            subject = email_type.render_subject(context)
            html = email_type.render_html(context)
            email_type.render_text(context)
            assert subject.strip(), f"{email_type.name}: empty subject"
            if email_type.html_content:
                assert html.strip(), f"{email_type.name}: empty html"

    def test_onboarding_sample_render_has_no_holes(self):
        onboarding = EmailType.objects.get(name='onboarding')
        html = onboarding.render_html(onboarding.get_sample_context_for_type())
        assert 'maria-hope' in html            # user.username
        assert 'C-BKM-7' in html               # participant_customer_number
        assert 'https://shop.example.org' in html  # participant_frontend_url

    def test_low_inventory_products_loop_renders(self):
        alert = EmailType.objects.get(name='low_inventory_alert')
        html = alert.render_html(alert.get_sample_context_for_type())
        assert 'Canned Beans' in html
        assert '12' in html

    def test_list_kind_variables_are_flagged(self):
        products = next(
            v for v in get_variables('low_inventory_alert')
            if v.token == 'products'
        )
        assert products.kind == 'list'
        assert 'name' in products.item_attributes

    def test_sample_context_includes_common_and_type_variables(self):
        context = build_sample_context('order_window_opened')
        assert context['user'].username == 'maria-hope'
        assert context['program_name']
        assert context['participant_customer_number']


# ---------------------------------------------------------------------------
# Migration 0017 wording
# ---------------------------------------------------------------------------

class TestOnboardingUsernameWording:

    def test_onboarding_leads_with_username(self):
        onboarding = EmailType.objects.get(name='onboarding')
        html = onboarding.html_content_en or onboarding.html_content
        text = onboarding.text_content_en or onboarding.text_content
        assert 'Your Username' in html
        assert '{{ user.username }}' in html
        assert 'Your Login Number' not in html
        assert 'You can also log in with your Customer Number' in html
        assert 'YOUR USERNAME: {{ user.username }}' in text
        assert '{{ participant_customer_number }}' in text


# ---------------------------------------------------------------------------
# Preview endpoint
# ---------------------------------------------------------------------------

class TestPreviewEndpoint:

    @pytest.fixture
    def staff_client(self):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(
                username='staff', email='staff@example.com', is_staff=True
            )
        )
        return client

    def _preview_url(self, name='onboarding'):
        email_type = EmailType.objects.get(name=name)
        return f'/api/v1/email-types/{email_type.pk}/preview/'

    def test_get_preview_renders_saved_content(self, staff_client):
        response = staff_client.get(self._preview_url())
        assert response.status_code == 200
        assert 'maria-hope' in response.data['html']
        assert '{{' not in response.data['subject']
        assert response.data['language'] == 'en'

    def test_get_preview_spanish(self, staff_client):
        response = staff_client.get(self._preview_url(), {'language': 'es'})
        assert response.status_code == 200
        assert response.data['language'] == 'es'

    def test_get_preview_rejects_unknown_language(self, staff_client):
        response = staff_client.get(self._preview_url(), {'language': 'fr'})
        assert response.status_code == 400
        assert response.data['field'] == 'language'

    def test_post_draft_renders_without_saving(self, staff_client):
        email_type = EmailType.objects.get(name='onboarding')
        original_html = email_type.html_content_en
        response = staff_client.post(
            self._preview_url(),
            {
                'html_content': '<p>Draft for {{ user.first_name }}</p>',
                'language': 'en',
            },
            format='json',
        )
        assert response.status_code == 200
        assert response.data['html'] == '<p>Draft for Maria</p>'
        # Omitted fields fall back to saved content.
        assert 'Welcome' in response.data['subject']
        email_type.refresh_from_db()
        assert email_type.html_content_en == original_html

    def test_post_bad_template_names_the_field(self, staff_client):
        response = staff_client.post(
            self._preview_url(),
            {'html_content': '{% for x in %}broken{% endfor %}', 'language': 'en'},
            format='json',
        )
        assert response.status_code == 400
        assert response.data['field'] == 'html_content'
        assert response.data['detail']

    def test_preview_is_staff_only(self):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(username='plain', email='p@example.com')
        )
        response = client.get(self._preview_url())
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Serializer translation columns + variables
# ---------------------------------------------------------------------------

class TestEmailTypeSerializerColumns:

    @pytest.fixture
    def staff_client(self):
        client = APIClient()
        client.force_authenticate(
            user=User.objects.create_user(
                username='staff2', email='staff2@example.com', is_staff=True
            )
        )
        return client

    def test_es_columns_round_trip(self, staff_client):
        email_type = EmailType.objects.get(name='onboarding')
        url = f'/api/v1/email-types/{email_type.pk}/'
        response = staff_client.patch(
            url, {'subject_es': '¡Bienvenida a Basketful!'}, format='json'
        )
        assert response.status_code == 200
        email_type.refresh_from_db()
        assert email_type.subject_es == '¡Bienvenida a Basketful!'
        assert staff_client.get(url).data['subject_es'] == '¡Bienvenida a Basketful!'

    def test_variables_exposed_per_type(self, staff_client):
        email_type = EmailType.objects.get(name='low_inventory_alert')
        response = staff_client.get(f'/api/v1/email-types/{email_type.pk}/')
        tokens = {v['token'] for v in response.data['variables']}
        assert 'products' in tokens
        assert 'user.first_name' in tokens
        products = next(
            v for v in response.data['variables'] if v['token'] == 'products'
        )
        assert products['kind'] == 'list'


# ---------------------------------------------------------------------------
# EmailSettings URL overrides
# ---------------------------------------------------------------------------

class TestEmailSettingsUrlOverrides:

    def test_fallback_to_env_settings_when_blank(self, settings):
        settings.PARTICIPANT_FRONTEND_URL = 'https://env.example.org'
        settings.DOMAIN_NAME = 'env-domain.example.org'
        email_settings = EmailSettings.get_settings()
        email_settings.participant_frontend_url = ''
        email_settings.backend_domain = ''
        email_settings.save()
        assert email_settings.get_participant_frontend_url() == 'https://env.example.org'
        assert email_settings.get_backend_domain() == 'env-domain.example.org'

    def test_overrides_win_when_set(self):
        email_settings = EmailSettings.get_settings()
        email_settings.participant_frontend_url = 'https://shop.override.org'
        email_settings.backend_domain = 'api.override.org'
        email_settings.save()
        assert email_settings.get_participant_frontend_url() == 'https://shop.override.org'
        assert email_settings.get_backend_domain() == 'api.override.org'

    def test_singleton_save_preserves_new_fields(self):
        EmailSettings.get_settings()
        duplicate = EmailSettings(
            from_email_default='new@example.org',
            reply_to_default='reply@example.org',
            participant_frontend_url='https://shop.copied.org',
            backend_domain='api.copied.org',
        )
        duplicate.save()
        assert EmailSettings.objects.count() == 1
        persisted = EmailSettings.get_settings()
        assert persisted.participant_frontend_url == 'https://shop.copied.org'
        assert persisted.backend_domain == 'api.copied.org'

    def test_build_email_context_uses_backend_domain_override(self):
        email_settings = EmailSettings.get_settings()
        email_settings.backend_domain = 'emails.example.org'
        email_settings.save()
        user = User.objects.create_user(
            username='ctx-user', email='ctx@example.com'
        )
        from apps.account.tasks.email import build_email_context
        context = build_email_context(user)
        assert context['domain'] == 'emails.example.org'
