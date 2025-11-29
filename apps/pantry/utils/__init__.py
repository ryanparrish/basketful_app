"""Utility functions for the pantry app."""
from django.core.exceptions import ObjectDoesNotExist
from apps.account.models import AccountBalance
from apps.voucher.models import Voucher


def get_active_vouchers(participant):
    """
    Return active vouchers for a participant, or an empty queryset if none.
    """
    try:
        account_balance = AccountBalance.active_accounts.get(
            participant=participant
        )
    except ObjectDoesNotExist:
        return Voucher.active_vouchers.none()
    return Voucher.active_vouchers.filter(
        account=account_balance,
        state=Voucher.APPLIED
    )
