"""Shared helpers for turning exceptions into safe API error responses."""
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response


def validation_error_text(error: ValidationError) -> str:
    """Join a ValidationError's messages into one readable sentence.

    ``str(error)`` returns the list repr (``"['msg']"``), which leaks Python
    formatting into the UI. The messages themselves are business-rule text
    written for the person using the app, so they are safe to show.
    """
    return ' '.join(error.messages)


def validation_error_response(error: ValidationError) -> Response:
    """Return a 400 whose ``error`` field carries the validation messages."""
    return Response(
        {'error': validation_error_text(error)},
        status=status.HTTP_400_BAD_REQUEST,
    )
