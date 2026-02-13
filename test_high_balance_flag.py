#!/usr/bin/env python
import os
import django

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
django.setup()

from apps.pantry.tests.factories import ParticipantFactory
from apps.voucher.models import VoucherSetting

# Ensure VoucherSetting exists
if not VoucherSetting.objects.filter(active=True).exists():
    VoucherSetting.objects.create(adult_amount=20, child_amount=12.5, infant_modifier=2.5, active=True)

# Test with high_balance=True
p = ParticipantFactory(adults=1, children=0, user=None, high_balance=True)
print(f'Participant: {p.name}')
print(f'User: {p.user}')
account = p.accountbalance
print(f'Base balance: {account.base_balance}')
print(f'Available balance: {account.available_balance}')
vouchers = list(account.vouchers.all())
print(f'Vouchers: {len(vouchers)}')
for v in vouchers:
    print(f'  - {v.voucher_type} state={v.state} multiplier={v.multiplier} active={v.active}')
