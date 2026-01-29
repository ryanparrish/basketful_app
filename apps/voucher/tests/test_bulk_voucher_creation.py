# apps/voucher/tests/test_bulk_voucher_creation.py
"""
Tests for bulk voucher creation views.

This module tests the three-step bulk voucher creation process:
1. Configuration - Select program, voucher type, and quantity
2. Preview - Review participants and select which ones to create vouchers for
3. Create - Execute the bulk creation

Uses pytest and Django's test client to test the admin views.
"""
import pytest
from decimal import Decimal
from unittest.mock import patch
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages

from apps.voucher.models import Voucher, VoucherSetting
from apps.account.models import Participant, AccountBalance
from apps.lifeskills.models import Program
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProgramFactory,
    VoucherSettingFactory,
)

User = get_user_model()


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def admin_user(db):
    """Create a staff/admin user for testing admin views."""
    # Mock celery tasks that trigger on user creation
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
    return user


@pytest.fixture
def admin_client(client, admin_user):
    """Return a logged-in admin client."""
    client.login(username='admin_test', password='testpass123')
    return client


@pytest.fixture
def voucher_setting(db):
    """Create an active voucher setting."""
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('50.00'),
        child_amount=Decimal('25.00'),
        infant_modifier=Decimal('10.00'),
        active=True
    )


@pytest.fixture
def program(db):
    """Create a test program."""
    return ProgramFactory(name='Test Program')


@pytest.fixture
def participants_with_accounts(db, program, voucher_setting):
    """
    Create multiple participants with accounts for the program.
    
    Returns a list of 3 participants, all with AccountBalance.
    """
    participants = []
    # Mock celery tasks that trigger on user/participant creation
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        for i in range(3):
            participant = ParticipantFactory(
                name=f'Test Participant {i}',
                program=program,
                active=True,
                adults=2,
                children=1
            )
            # Ensure account exists (factory should create it, but be explicit)
            AccountBalance.objects.get_or_create(
                participant=participant,
                defaults={'base_balance': Decimal('100.00')}
            )
            participants.append(participant)
    return participants


@pytest.fixture
def participant_without_account(db, program):
    """
    Create a participant without an AccountBalance.
    
    Manually delete the account if the signal creates one.
    """
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        participant = Participant.objects.create(
            name='No Account Participant',
            email='noaccount@test.com',
            program=program,
            active=True,
            adults=1,
            children=0
        )
    # Delete any auto-created account
    AccountBalance.objects.filter(participant=participant).delete()
    return participant


# ============================================================
# Configuration View Tests (Step 1)
# ============================================================

@pytest.mark.django_db
class TestBulkVoucherConfigure:
    """Tests for the bulk voucher configuration view (Step 1)."""
    
    def test_configure_view_requires_staff(self, client, program):
        """Non-staff users should be redirected to login."""
        url = reverse('admin:bulk_voucher_configure')
        response = client.get(url)
        assert response.status_code == 302
        assert '/admin/login/' in response.url or '/login/' in response.url
    
    def test_configure_view_accessible_to_staff(self, admin_client, program):
        """Staff users should access the configuration page."""
        url = reverse('admin:bulk_voucher_configure')
        response = admin_client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context
    
    def test_configure_form_submission_valid(self, admin_client, program):
        """Valid form submission should redirect to preview."""
        url = reverse('admin:bulk_voucher_configure')
        data = {
            'program': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 2,
            'notes': 'Test bulk creation',
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == 302
        assert 'preview' in response.url
        
        # Check session data was stored
        session = admin_client.session
        config = session.get('bulk_voucher_config')
        assert config is not None
        assert config['program_id'] == program.id
        assert config['voucher_type'] == 'grocery'
        assert config['vouchers_per_participant'] == 2
        assert config['notes'] == 'Test bulk creation'
    
    def test_configure_form_submission_invalid_missing_program(self, admin_client):
        """Form without program should show errors."""
        url = reverse('admin:bulk_voucher_configure')
        data = {
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
        }
        response = admin_client.post(url, data)
        
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors


# ============================================================
# Preview View Tests (Step 2)
# ============================================================

@pytest.mark.django_db
class TestBulkVoucherPreview:
    """Tests for the bulk voucher preview view (Step 2)."""
    
    def test_preview_without_config_redirects(self, admin_client):
        """Accessing preview without configuration should redirect."""
        url = reverse('admin:bulk_voucher_preview')
        response = admin_client.get(url)
        
        assert response.status_code == 302
        # Redirects to configure page (bulk-create is the base URL)
        assert 'bulk-create' in response.url
    
    def test_preview_shows_participants(
        self, admin_client, program, participants_with_accounts
    ):
        """Preview should display participants with accounts."""
        # Set up session config
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': 'Test',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_preview')
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert 'participant_list' in response.context
        assert len(response.context['participant_list']) == 3
    
    def test_preview_shows_participants_without_account(
        self, admin_client, program, participants_with_accounts, participant_without_account
    ):
        """Preview should identify participants without accounts."""
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_preview')
        response = admin_client.get(url)
        
        assert response.status_code == 200
        assert 'participants_without_account' in response.context
        # The participant without account should be flagged
        no_account_list = response.context['participants_without_account']
        assert any(p.id == participant_without_account.id for p in no_account_list)
    
    def test_preview_post_without_selection_shows_error(
        self, admin_client, program, participants_with_accounts
    ):
        """POST without selecting participants should show error."""
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_preview')
        response = admin_client.post(url, {
            'selected_participants': [],
            'confirmation': True,
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        })
        
        assert response.status_code == 200
        messages_list = list(get_messages(response.wsgi_request))
        assert any('select at least one' in str(m).lower() for m in messages_list)
    
    def test_preview_post_with_selection_stores_ids(
        self, admin_client, program, participants_with_accounts
    ):
        """POST with selection should store participant IDs in session."""
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        }
        session.save()
        
        selected_ids = [str(p.id) for p in participants_with_accounts[:2]]
        
        url = reverse('admin:bulk_voucher_preview')
        response = admin_client.post(url, {
            'selected_participants': selected_ids,
            'confirmation': True,
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        })
        
        assert response.status_code == 302
        
        # Check session was updated with selected IDs
        session = admin_client.session
        config = session.get('bulk_voucher_config')
        assert 'selected_participant_ids' in config
        assert len(config['selected_participant_ids']) == 2


# ============================================================
# Create View Tests (Step 3)
# ============================================================

@pytest.mark.django_db
class TestBulkVoucherCreate:
    """Tests for the bulk voucher creation view (Step 3)."""
    
    def test_create_without_config_redirects(self, admin_client):
        """Accessing create without configuration should redirect."""
        url = reverse('admin:bulk_voucher_create')
        response = admin_client.get(url)
        
        assert response.status_code == 302
        # Redirects to configure page (bulk-create is the base URL)
        assert 'bulk-create' in response.url
    
    def test_create_vouchers_for_all_participants(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Should create vouchers for all participants when no selection made."""
        # Clear any existing vouchers
        Voucher.objects.all().delete()
        
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 2,
            'notes': 'Bulk test',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_create')
        response = admin_client.get(url)
        
        assert response.status_code == 302
        
        # Should have created 3 participants × 2 vouchers = 6 vouchers
        assert Voucher.objects.count() == 6
        
        # Verify voucher properties
        voucher = Voucher.objects.first()
        assert voucher.voucher_type == 'grocery'
        assert voucher.state == Voucher.PENDING
        assert 'Bulk test' in voucher.notes
    
    def test_create_vouchers_for_selected_participants_only(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Should create vouchers only for selected participants."""
        Voucher.objects.all().delete()
        
        selected_participant = participants_with_accounts[0]
        
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'life',
            'vouchers_per_participant': 3,
            'notes': 'Selected only',
            'selected_participant_ids': [selected_participant.id],
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_create')
        response = admin_client.get(url)
        
        assert response.status_code == 302
        
        # Should have created 1 participant × 3 vouchers = 3 vouchers
        assert Voucher.objects.count() == 3
        
        # All vouchers should be for the selected participant
        account = AccountBalance.objects.get(participant=selected_participant)
        assert Voucher.objects.filter(account=account).count() == 3
    
    def test_create_skips_participants_without_account(
        self, admin_client, program, participants_with_accounts, 
        participant_without_account, voucher_setting
    ):
        """Should skip participants without AccountBalance and show warning."""
        Voucher.objects.all().delete()
        
        # Include the participant without account in selection
        all_ids = [p.id for p in participants_with_accounts] + [participant_without_account.id]
        
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
            'selected_participant_ids': all_ids,
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_create')
        response = admin_client.get(url)
        
        assert response.status_code == 302
        
        # Should only create vouchers for 3 participants (not the one without account)
        assert Voucher.objects.count() == 3
        
        # Check warning message about skipped participant
        messages_list = list(get_messages(response.wsgi_request))
        has_warning = any('skipped' in str(m).lower() for m in messages_list)
        assert has_warning
    
    def test_create_clears_session_after_success(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Session config should be cleared after successful creation."""
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': '',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_create')
        admin_client.get(url)
        
        # Refresh session
        session = admin_client.session
        assert session.get('bulk_voucher_config') is None
    
    def test_create_shows_success_message(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Should show success message with count of created vouchers."""
        Voucher.objects.all().delete()
        
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 2,
            'notes': '',
        }
        session.save()
        
        url = reverse('admin:bulk_voucher_create')
        response = admin_client.get(url)
        
        messages_list = list(get_messages(response.wsgi_request))
        success_messages = [m for m in messages_list if 'success' in str(m.tags).lower()]
        assert len(success_messages) > 0
        assert '6' in str(success_messages[0])  # 3 participants × 2 vouchers


# ============================================================
# Integration Tests
# ============================================================

@pytest.mark.django_db
class TestBulkVoucherFullFlow:
    """Integration tests for the complete bulk voucher creation flow."""
    
    def test_full_creation_flow(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Test the complete flow from configuration to creation."""
        Voucher.objects.all().delete()
        
        # Step 1: Configure
        config_url = reverse('admin:bulk_voucher_configure')
        config_response = admin_client.post(config_url, {
            'program': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': 'Full flow test',
        })
        assert config_response.status_code == 302
        
        # Step 2: Preview and select
        preview_url = reverse('admin:bulk_voucher_preview')
        preview_response = admin_client.post(preview_url, {
            'selected_participants': [str(p.id) for p in participants_with_accounts],
            'confirmation': True,
            'program_id': program.id,
            'voucher_type': 'grocery',
            'vouchers_per_participant': 1,
            'notes': 'Full flow test',
        })
        assert preview_response.status_code == 302
        
        # Step 3: Create
        create_url = reverse('admin:bulk_voucher_create')
        create_response = admin_client.get(create_url)
        assert create_response.status_code == 302
        
        # Verify results
        assert Voucher.objects.count() == 3
        for voucher in Voucher.objects.all():
            assert voucher.voucher_type == 'grocery'
            assert voucher.state == Voucher.PENDING
            assert 'Full flow test' in voucher.notes
    
    def test_flow_with_life_vouchers(
        self, admin_client, program, participants_with_accounts, voucher_setting
    ):
        """Test creating life vouchers through the flow."""
        Voucher.objects.all().delete()
        
        # Configure for life vouchers
        session = admin_client.session
        session['bulk_voucher_config'] = {
            'program_id': program.id,
            'voucher_type': 'life',
            'vouchers_per_participant': 1,
            'notes': 'Life voucher test',
            'selected_participant_ids': [participants_with_accounts[0].id],
        }
        session.save()
        
        # Create
        create_url = reverse('admin:bulk_voucher_create')
        admin_client.get(create_url)
        
        assert Voucher.objects.count() == 1
        voucher = Voucher.objects.first()
        assert voucher.voucher_type == 'life'
