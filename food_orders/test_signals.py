from decimal import Decimal
from django.test import TestCase
from .models import AccountBalance, Voucher, Participant, VoucherSetting
from .balance_utils import calculate_base_balance

class ParticipantSignalsTest(TestCase):

    def setUp(self):
        # Create an active VoucherSetting for all tests
        self.voucher_setting = VoucherSetting.objects.create(
            adult_amount=10,
            child_amount=5,
            infant_modifier=2,
            active=True
        )

    def create_participant_with_defaults(self, **kwargs):
        """Helper to create a participant with default counts if not provided."""
        defaults = {'adults': 1, 'children': 1, 'diaper_count': 1}
        defaults.update(kwargs)
        participant = Participant.objects.create(
            name=kwargs.get('name', 'Test User'),
            email=kwargs.get('email', 'test@test.com'),
            adults=defaults['adults'],
            children=defaults['children'],
            diaper_count=defaults['diaper_count']
        )
        return participant

    def test_account_and_vouchers_created_on_participant_create(self):
        participant = self.create_participant_with_defaults()

        # Check that AccountBalance was created
        self.assertTrue(hasattr(participant, 'accountbalance'))

        # Check that 2 grocery vouchers were created
        vouchers = Voucher.objects.filter(account__participant=participant, voucher_type="grocery")
        self.assertEqual(vouchers.count(), 2)

    def test_no_account_created_on_update(self):
        participant = self.create_participant_with_defaults()
        participant.name = "Updated Name"
        participant.save()

        # Ensure only 1 account exists and no extra vouchers were created
        self.assertEqual(AccountBalance.objects.filter(participant=participant).count(), 1)
        self.assertEqual(Voucher.objects.filter(account__participant=participant).count(), 2)

    def test_base_balance_updated_on_each_field_change(self):
    # Create a participant with initial counts
        participant = self.create_participant_with_defaults()
        account_balance = participant.accountbalance

        # Track the initial balance
        initial_balance = account_balance.base_balance

        # Define changes for each relevant field
        field_updates = {
            'adults': 3,
            'children': 2,
            'diaper_count': 4,
        }

        for field, new_value in field_updates.items():
            with self.subTest(field=field):
                # Update the field
                setattr(participant, field, new_value)
                participant.save()  # triggers the signal
                account_balance.refresh_from_db()

                # Assert that the balance increased
                self.assertGreater(account_balance.base_balance, initial_balance)

                # Update initial_balance for the next subTest
                initial_balance = account_balance.base_balance
