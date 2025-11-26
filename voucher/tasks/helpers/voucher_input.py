# tasks/helpers/voucher_input.py

def normalize_voucher_ids(voucher_ids):
    """Ensure voucher_ids is always a clean list of ints."""
    if not voucher_ids:
        return []

    if isinstance(voucher_ids, int):
        return [voucher_ids]

    if hasattr(voucher_ids, "__iter__"):
        return list(voucher_ids)

    return [voucher_ids]
