"""Central registry of template variables available to each email type.

This is the contract between the senders (which assemble real context in
apps/account/tasks/email.py, apps/account/tasks/order_window.py and
apps/pantry/tasks/low_inventory.py) and the email design studio's
variable picker + sample-data preview. When a sender adds a context key,
add it here so staff can discover it and previews render realistically.

``kind`` values:
- ``value``  — a simple substitution token, safe to insert into any
  text block as ``{{ token }}``.
- ``list``   — an iterable rendered with ``{% for %}``; only usable in
  raw-HTML blocks or code mode, and flagged as such in the UI.
"""
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, List


@dataclass(frozen=True)
class EmailVariable:
    token: str
    label: str
    description: str
    sample_value: Any
    kind: str = 'value'
    # For kind='list': item attributes usable inside the loop.
    item_attributes: tuple = field(default_factory=tuple)


def _sample_user():
    return SimpleNamespace(
        first_name='Maria',
        last_name='Garcia',
        username='maria-hope',
        email='maria.garcia@example.com',
        get_username=lambda: 'maria-hope',
    )


COMMON_VARIABLES: List[EmailVariable] = [
    EmailVariable(
        'user.first_name', "Recipient's first name",
        'First name of the person receiving the email.', 'Maria'),
    EmailVariable(
        'user.last_name', "Recipient's last name",
        'Last name of the person receiving the email.', 'Garcia'),
    EmailVariable(
        'user.username', "Recipient's username",
        'The username the person types to log in.', 'maria-hope'),
    EmailVariable(
        'user.email', "Recipient's email address",
        'Email address the message is sent to.', 'maria.garcia@example.com'),
    EmailVariable(
        'site_name', 'Site name',
        'The name of this system.', 'Basketful'),
    EmailVariable(
        'domain', 'Backend domain',
        'Domain used for backend links such as password reset.',
        'example.com'),
    EmailVariable(
        'protocol', 'Link protocol',
        'http or https, used when building links.', 'https'),
]

_PARTICIPANT_FRONTEND_URL = EmailVariable(
    'participant_frontend_url', 'Participant app URL',
    'Where participants shop and log in. Configured under Settings → Email.',
    'https://shop.example.org')

_PARTICIPANT_CUSTOMER_NUMBER = EmailVariable(
    'participant_customer_number', 'Customer number',
    "The participant's warehouse customer number (also accepted at login).",
    'C-BKM-7')

EMAIL_TYPE_VARIABLES = {
    'onboarding': [
        _PARTICIPANT_FRONTEND_URL,
        _PARTICIPANT_CUSTOMER_NUMBER,
        EmailVariable(
            'uid', 'Password-reset UID',
            'Part of the password-reset link (advanced).', 'sample-uid-123'),
        EmailVariable(
            'token', 'Password-reset token',
            'Part of the password-reset link (advanced).', 'sample-token-abc'),
    ],
    'password_reset': [
        EmailVariable(
            'uid', 'Password-reset UID',
            'Part of the password-reset link (advanced).', 'sample-uid-123'),
        EmailVariable(
            'token', 'Password-reset token',
            'Part of the password-reset link (advanced).', 'sample-token-abc'),
    ],
    'order_window_opened': [
        EmailVariable(
            'program_name', 'Program name',
            "The participant's program.", 'Tuesday Morning Life Skills'),
        EmailVariable(
            'closes_at', 'Window closes at',
            'When the order window closes, already formatted for display.',
            'Tuesday, July 14 at 8:00 AM'),
        EmailVariable(
            'participant_name', "Participant's name",
            'Display name of the participant.', 'Maria Garcia'),
        _PARTICIPANT_CUSTOMER_NUMBER,
        _PARTICIPANT_FRONTEND_URL,
    ],
    'low_inventory_alert': [
        EmailVariable(
            'products', 'Low-stock products',
            'The products at or below the threshold. Loop with '
            '{% for product in products %} — product.name, '
            'product.quantity_in_stock.',
            None, kind='list',
            item_attributes=('name', 'quantity_in_stock')),
        EmailVariable(
            'threshold', 'Low-stock threshold',
            'The configured alert threshold.', 45),
        EmailVariable(
            'product_count', 'Product count',
            'How many products are in this alert.', 2),
    ],
    # Seeded but inactive placeholders — common variables only.
    'order_confirmation': [],
    'voucher_notification': [],
}

_SAMPLE_OVERRIDES = {
    'low_inventory_alert': lambda: {
        'products': [
            SimpleNamespace(name='Canned Beans', quantity_in_stock=12),
            SimpleNamespace(name='Rice (2 lb)', quantity_in_stock=31),
        ],
    },
}


def get_variables(email_type_name):
    """All variables available to an email type (common + type-specific)."""
    return COMMON_VARIABLES + EMAIL_TYPE_VARIABLES.get(email_type_name, [])


def build_sample_context(email_type_name=None):
    """Realistic sample context for previewing an email type.

    Mirrors build_email_context() plus the sender's extra_context for the
    given type, using the registry's sample values.
    """
    context = {'user': _sample_user()}
    for variable in get_variables(email_type_name):
        if '.' in variable.token:
            continue  # nested tokens (user.*) come from the objects above
        context[variable.token] = variable.sample_value
    overrides = _SAMPLE_OVERRIDES.get(email_type_name)
    if overrides:
        context.update(overrides())
    return context
