"""Tests for apps.api.errors — safe exception-to-response helpers (#149)."""
from django.core.exceptions import ValidationError

from apps.api.errors import validation_error_response, validation_error_text


def test_single_message_has_no_list_repr():
    error = ValidationError('Cannot cancel a completed order.')
    assert validation_error_text(error) == 'Cannot cancel a completed order.'


def test_multiple_messages_are_joined_into_one_sentence():
    error = ValidationError(['Food balance exceeded.', 'Hygiene limit reached.'])
    assert validation_error_text(error) == 'Food balance exceeded. Hygiene limit reached.'


def test_field_keyed_errors_are_flattened():
    error = ValidationError({'status': ['Invalid transition.']})
    assert validation_error_text(error) == 'Invalid transition.'


def test_response_is_400_with_error_field():
    response = validation_error_response(ValidationError('Nope.'))
    assert response.status_code == 400
    assert response.data == {'error': 'Nope.'}
