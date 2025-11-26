# core/middleware.py
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import redirect
from log.models import OrderValidationLog

logger = logging.getLogger("custom_validation")


class GlobalErrorMiddleware:
    """
    Middleware that unifies error handling:
    - ValidationError → user-friendly message + safe redirect
        - DEBUG=True → debug log
        - DEBUG=False → persist to OrderValidationLog
    - Other unhandled exceptions:
        - DEBUG=True → Django default error page
        - DEBUG=False → log + safe redirect
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            # Let Django show full tracebacks in dev
            return self.get_response(request)

        try:
            return self.get_response(request)

        except ValidationError as e:
            self.handle_validation_error(request, e)

            # For non-admin/API paths → redirect with toast
            if not (
                request.path.startswith("/admin/") or request.path.startswith("/api/")
            ):
                messages.error(request, str(e))
                return redirect("participant_dashboard")

            # Let admin/API bubble the error
            raise e

        except Exception as e:  # pylint: disable=broad-except
            # Log and fallback redirect for unhandled errors
            logger.exception("Unhandled exception on path=%s", request.path, exc_info=e)
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("home")  # Safe fallback page

    def handle_validation_error(self, request, exception):
        """Log ValidationError details appropriately based on DEBUG setting."""
        user = getattr(request, "user", None)
        participant = getattr(user, "participant", None)

        if settings.DEBUG:
            logger.debug(
                "ValidationError on path=%s, user=%s, participant=%s, error=%s",
                request.path,
                getattr(user, "username", "Anonymous"),
                getattr(participant, "id", None),
                exception
            )
        else:
            OrderValidationLog.objects.create(  # pylint: disable=no-member
                user=user if user and user.is_authenticated else None,
                participant=participant,
                message=str(exception),
                log_type=OrderValidationLog.ERROR,
            )
