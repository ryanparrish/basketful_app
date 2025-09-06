from django.test import TestCase
from .models import Participant
from .models import AccountBalance, Voucher

class ParticipantSignalsTest(TestCase):

    def test_account_and_vouchers_created_on_participant_create(self):
        participant = Participant.objects.create(name="Test User", email="test@testmail.com")
        
        # Check that account was created
        self.assertTrue(hasattr(participant, 'accountbalance'))
        
        # Check that 2 grocery vouchers were created
        vouchers = Voucher.objects.filter(account__participant=participant, voucher_type="grocery")
        self.assertEqual(vouchers.count(), 2)

    def test_no_account_created_on_update(self):
        participant = Participant.objects.create(name="Test User", email="test@test.com")
        participant.name = "Updated Name"
        participant.save()
        
        # Ensure only 1 account exists and no extra vouchers were created
        self.assertEqual(AccountBalance.objects.filter(participant=participant).count(), 1)
        self.assertEqual(Voucher.objects.filter(account__participant=participant).count(), 2)
