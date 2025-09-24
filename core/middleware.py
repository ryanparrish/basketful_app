# core/middleware.py
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import redirect
from food_orders.models import OrderValidationLog  # concrete log model

logger = logging.getLogger("custom_validation")


class ValidationMiddleware:
    """
    Middleware to handle ValidationErrors globally:
    - In DEBUG mode: logs to logger.debug
    - In production: logs to OrderValidationLog
    - Non-admin/API requests: show messages and redirect to participant dashboard
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ValidationError as e:
            self.handle_validation_error(request, e)
            # Show message & redirect for non-admin/API paths
            if not (request.path.startswith("/admin/") or request.path.startswith("/api/")):
                messages.error(request, str(e))
                return redirect("participant_dashboard")
            # Otherwise, re-raise for API/admin to handle
            raise

    def handle_validation_error(self, request, exception):
        user = getattr(request, "user", None)
        participant = getattr(user, "participant", None)

        if settings.DEBUG:
            # Developer-friendly debug log
            logger.debug(
                f"ValidationError on path={request.path}, "
                f"user={getattr(user, 'username', 'Anonymous')}, "
                f"participant={getattr(participant, 'id', None)}: {exception}"
            )
        else:
            # Persist to OrderValidationLog in production
            OrderValidationLog.objects.create(
                user=user if user and user.is_authenticated else None,
                participant=participant,
                message=str(exception),
                log_type=OrderValidationLog.ERROR,  # mark as error log
            )
