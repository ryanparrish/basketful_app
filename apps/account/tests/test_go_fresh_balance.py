"""
Tests for Go Fresh balance calculations.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from apps.account.models import GoFreshSettings, Participant, AccountBalance
from apps.pantry.tests.factories import ParticipantFactory


@pytest.mark.django_db
class TestGoFreshBalanceCalculations:
    """Test Go Fresh balance calculation logic."""
    
    def test_small_household_1_person(self):
        """1-person household should get small budget ($10)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=1, children=0)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('10.00')
        assert balance == settings.small_household_budget
    
    def test_small_household_2_people(self):
        """2-person household should get small budget ($10)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=2, children=0)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('10.00')
        assert balance == settings.small_household_budget
    
    def test_medium_household_3_people(self):
        """3-person household should get medium budget ($20)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=2, children=1)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('20.00')
        assert balance == settings.medium_household_budget
    
    def test_medium_household_5_people(self):
        """5-person household should get medium budget ($20)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=2, children=3)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('20.00')
        assert balance == settings.medium_household_budget
    
    def test_large_household_6_people(self):
        """6-person household should get large budget ($25)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=3, children=3)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('25.00')
        assert balance == settings.large_household_budget
    
    def test_large_household_10_people(self):
        """10-person household should get large budget ($25)."""
        settings = GoFreshSettings.get_settings()
        participant = ParticipantFactory(adults=5, children=5)
        
        balance = participant.accountbalance.go_fresh_balance
        assert balance == Decimal('25.00')
        assert balance == settings.large_household_budget
    
    def test_disabled_settings_returns_zero(self):
        """When Go Fresh is disabled, balance should be 0."""
        settings = GoFreshSettings.get_settings()
        settings.enabled = False
        settings.save()
        
        participant = ParticipantFactory(adults=2, children=2)
        balance = participant.accountbalance.go_fresh_balance
        
        assert balance == Decimal('0')
        
        # Re-enable for other tests
        settings.enabled = True
        settings.save()
    
    def test_custom_thresholds(self):
        """Test with custom threshold configuration."""
        settings = GoFreshSettings.get_settings()
        settings.small_threshold = 3
        settings.large_threshold = 8
        settings.save()
        
        # 3 people should get small budget
        participant1 = ParticipantFactory(adults=2, children=1)
        assert participant1.accountbalance.go_fresh_balance == settings.small_household_budget
        
        # 5 people should get medium budget
        participant2 = ParticipantFactory(adults=3, children=2)
        assert participant2.accountbalance.go_fresh_balance == settings.medium_household_budget
        
        # 8 people should get large budget
        participant3 = ParticipantFactory(adults=4, children=4)
        assert participant3.accountbalance.go_fresh_balance == settings.large_household_budget
        
        # Reset to defaults
        settings.small_threshold = 2
        settings.large_threshold = 6
        settings.save()
    
    def test_balances_method_includes_go_fresh(self):
        """Participant.balances() should include go_fresh_balance."""
        participant = ParticipantFactory(adults=2, children=2)
        balances = participant.balances()
        
        assert 'go_fresh_balance' in balances
        assert 'full_balance' in balances
        assert 'available_balance' in balances
        assert 'hygiene_balance' in balances
        assert balances['go_fresh_balance'] == Decimal('20.00')


@pytest.mark.django_db
class TestGoFreshSettingsValidation:
    """Test GoFreshSettings model validation."""
    
    def test_small_threshold_must_be_less_than_large(self):
        """Small threshold must be less than large threshold."""
        settings = GoFreshSettings.get_settings()
        settings.small_threshold = 6
        settings.large_threshold = 2
        
        with pytest.raises(ValidationError) as exc_info:
            settings.clean()
        
        assert 'Small threshold must be less than large threshold' in str(exc_info.value)
    
    def test_equal_thresholds_fails_validation(self):
        """Equal thresholds should fail validation."""
        settings = GoFreshSettings.get_settings()
        settings.small_threshold = 5
        settings.large_threshold = 5
        
        with pytest.raises(ValidationError):
            settings.clean()
    
    def test_positive_budgets_required(self):
        """All budgets must be positive."""
        settings = GoFreshSettings.get_settings()
        
        # Test small budget
        settings.small_household_budget = Decimal('0')
        with pytest.raises(ValidationError) as exc_info:
            settings.clean()
        assert 'Small household budget must be positive' in str(exc_info.value)
        
        # Reset and test medium budget
        settings.small_household_budget = Decimal('10.00')
        settings.medium_household_budget = Decimal('-5.00')
        with pytest.raises(ValidationError) as exc_info:
            settings.clean()
        assert 'Medium household budget must be positive' in str(exc_info.value)
    
    def test_singleton_enforcement(self):
        """Only one GoFreshSettings instance should exist."""
        settings1 = GoFreshSettings.get_settings()
        assert settings1.pk == 1
        
        # Trying to create another should update the first
        settings2 = GoFreshSettings(
            small_household_budget=Decimal('15.00'),
            enabled=False
        )
        settings2.save()
        
        # Should only be one instance
        assert GoFreshSettings.objects.count() == 1
        
        # Should have updated values
        updated = GoFreshSettings.objects.get(pk=1)
        assert updated.small_household_budget == Decimal('15.00')
        assert updated.enabled is False
    
    def test_get_settings_creates_if_missing(self):
        """get_settings() should create settings if they don't exist."""
        GoFreshSettings.objects.all().delete()
        
        settings = GoFreshSettings.get_settings()
        
        assert settings is not None
        assert settings.pk == 1
        assert settings.enabled is True
        assert settings.small_household_budget == Decimal('10.00')
