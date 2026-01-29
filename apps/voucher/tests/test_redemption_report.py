# apps/voucher/tests/test_redemption_report.py
"""Tests for voucher redemption report."""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.lifeskills.models import Program
from apps.account.models import Participant, AccountBalance
from apps.voucher.models import Voucher, VoucherSetting, OrderVoucher
from apps.voucher.views_reports import _get_date_range, _get_redemption_data
from apps.orders.models import Order
from apps.orders.tests.factories import (
    ParticipantFactory,
    ProgramFactory,
    VoucherSettingFactory,
)


User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user for testing."""
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        return User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )


@pytest.fixture
def program(db):
    """Create a test program."""
    return ProgramFactory(name='Test Program')


@pytest.fixture
def second_program(db):
    """Create a second test program."""
    return ProgramFactory(name='Second Program')


@pytest.fixture
def voucher_setting(db):
    """Create active voucher settings."""
    VoucherSetting.objects.all().update(active=False)
    return VoucherSetting.objects.create(
        adult_amount=Decimal('20.00'),
        child_amount=Decimal('12.50'),
        infant_modifier=Decimal('0.00'),
        active=True
    )


@pytest.fixture
def participant_with_account(db, program, voucher_setting):
    """Create a participant with account balance."""
    with patch('apps.pantry.signals.send_new_user_onboarding_email.delay'):
        participant = ParticipantFactory(
            name='Test Participant',
            program=program,
            active=True,
            adults=2,
            children=0
        )
        account, _ = AccountBalance.objects.get_or_create(
            participant=participant,
            defaults={'base_balance': Decimal('0.00')}
        )
    return participant, account


@pytest.fixture
def consumed_voucher(db, participant_with_account, voucher_setting):
    """Create a consumed voucher."""
    participant, account = participant_with_account
    voucher = Voucher.objects.create(
        account=account,
        voucher_type='grocery',
        active=False,
        notes='Test consumed voucher'
    )
    # Manually set state since it's not editable
    Voucher.objects.filter(pk=voucher.pk).update(state=Voucher.CONSUMED)
    voucher.refresh_from_db()
    return voucher


class TestGetDateRange:
    """Tests for _get_date_range helper function."""
    
    def test_this_week(self):
        """Test this week calculation."""
        start, end = _get_date_range('this_week')
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        assert end == today
        assert start == start_of_week
    
    def test_this_month(self):
        """Test this month calculation."""
        start, end = _get_date_range('this_month')
        today = date.today()
        assert end == today
        assert start == today.replace(day=1)
    
    def test_last_month(self):
        """Test last month calculation."""
        start, end = _get_date_range('last_month')
        today = date.today()
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        first_of_last_month = last_of_last_month.replace(day=1)
        
        assert start == first_of_last_month
        assert end == last_of_last_month
    
    def test_this_year(self):
        """Test this year calculation."""
        start, end = _get_date_range('this_year')
        today = date.today()
        assert start == date(today.year, 1, 1)
        assert end == today
    
    def test_custom_range(self):
        """Test custom date range."""
        custom_start = date(2025, 1, 1)
        custom_end = date(2025, 1, 31)
        start, end = _get_date_range('custom', custom_start, custom_end)
        assert start == custom_start
        assert end == custom_end


@pytest.mark.django_db
class TestGetRedemptionData:
    """Tests for _get_redemption_data helper function."""
    
    def test_empty_data_returns_empty_dict(self):
        """Test that no vouchers returns empty dict."""
        start = date.today() - timedelta(days=30)
        end = date.today()
        result = _get_redemption_data(start, end)
        assert result == {}
    
    def test_consumed_voucher_counted(self, consumed_voucher, program):
        """Test that consumed vouchers are counted."""
        start = date.today() - timedelta(days=1)
        end = date.today() + timedelta(days=1)
        result = _get_redemption_data(start, end)
        
        assert program.name in result
        assert result[program.name]['voucher_count'] == 1
        assert result[program.name]['grocery_count'] == 1
        assert result[program.name]['life_count'] == 0
    
    def test_filter_by_program(self, consumed_voucher, program, second_program):
        """Test filtering by specific program."""
        start = date.today() - timedelta(days=1)
        end = date.today() + timedelta(days=1)
        
        # Filter by the program with the voucher
        result = _get_redemption_data(start, end, program=program)
        assert program.name in result
        
        # Filter by the other program
        result2 = _get_redemption_data(start, end, program=second_program)
        assert result2 == {}
    
    def test_filter_by_voucher_type(self, consumed_voucher, program):
        """Test filtering by voucher type."""
        start = date.today() - timedelta(days=1)
        end = date.today() + timedelta(days=1)
        
        # Filter for grocery (should find it)
        result = _get_redemption_data(start, end, voucher_type='grocery')
        assert program.name in result
        
        # Filter for life (should not find it)
        result2 = _get_redemption_data(start, end, voucher_type='life')
        assert result2 == {}


@pytest.mark.django_db
class TestVoucherRedemptionReportView:
    """Tests for the voucher redemption report view."""
    
    def test_view_requires_staff(self, client):
        """Test that the view requires staff member."""
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url)
        # Should redirect to login
        assert response.status_code == 302
        assert '/login/' in response.url or '/admin/login/' in response.url
    
    def test_view_accessible_by_admin(self, client, admin_user):
        """Test that admin users can access the view."""
        client.login(username='admin', password='testpass123')
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url)
        assert response.status_code == 200
        assert 'Voucher Redemption Report' in response.content.decode()
    
    def test_view_with_date_range(self, client, admin_user):
        """Test view with date range parameter."""
        client.login(username='admin', password='testpass123')
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url, {'date_range': 'this_week', 'group_by': 'program'})
        assert response.status_code == 200
        assert 'Report Period' in response.content.decode()
    
    def test_view_custom_range_requires_dates(self, client, admin_user):
        """Test that custom range requires start and end dates."""
        client.login(username='admin', password='testpass123')
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url, {'date_range': 'custom'})
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Start date is required' in content or 'End date is required' in content
    
    def test_view_with_consumed_vouchers(self, client, admin_user, consumed_voucher, program):
        """Test view shows consumed vouchers in report."""
        client.login(username='admin', password='testpass123')
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url, {'date_range': 'last_30_days'})
        assert response.status_code == 200
        content = response.content.decode()
        assert program.name in content
    
    def test_pdf_export(self, client, admin_user, consumed_voucher):
        """Test PDF export functionality."""
        client.login(username='admin', password='testpass123')
        url = reverse('admin:voucher_redemption_report')
        response = client.get(url, {
            'date_range': 'this_month',
            'group_by': 'program',
            'export_pdf': '1'
        })
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/pdf'
        assert 'attachment; filename=' in response['Content-Disposition']


@pytest.mark.django_db
class TestVoucherRedemptionReportForm:
    """Tests for VoucherRedemptionReportForm."""
    
    def test_form_valid_with_preset_range(self):
        """Test form is valid with preset date range."""
        from apps.voucher.forms import VoucherRedemptionReportForm
        form = VoucherRedemptionReportForm(data={
            'date_range': 'this_week',
            'group_by': 'program'
        })
        assert form.is_valid()
    
    def test_form_valid_with_custom_range(self):
        """Test form is valid with custom date range."""
        from apps.voucher.forms import VoucherRedemptionReportForm
        form = VoucherRedemptionReportForm(data={
            'date_range': 'custom',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'group_by': 'program'
        })
        assert form.is_valid()
    
    def test_form_invalid_custom_without_dates(self):
        """Test form is invalid with custom range but no dates."""
        from apps.voucher.forms import VoucherRedemptionReportForm
        form = VoucherRedemptionReportForm(data={
            'date_range': 'custom'
        })
        assert not form.is_valid()
        assert 'start_date' in form.errors or 'end_date' in form.errors
    
    def test_form_invalid_end_before_start(self):
        """Test form is invalid when end date is before start date."""
        from apps.voucher.forms import VoucherRedemptionReportForm
        form = VoucherRedemptionReportForm(data={
            'date_range': 'custom',
            'start_date': '2025-01-31',
            'end_date': '2025-01-01'
        })
        assert not form.is_valid()
        assert 'end_date' in form.errors
