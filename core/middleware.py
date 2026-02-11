# core/middleware.py
"""Middleware for global error handling, logging, and security headers."""
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import redirect
from apps.log.models import OrderValidationLog

logger = logging.getLogger("custom_validation")


class SecurityHeadersMiddleware:
    """
    Middleware that adds security headers to all responses.
    
    Headers added:
    - Content-Security-Policy: Restricts resource loading
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-Frame-Options: Prevents clickjacking
    - Strict-Transport-Security: Enforces HTTPS
    - Referrer-Policy: Controls referrer information
    - Permissions-Policy: Restricts browser features
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Content-Security-Policy
        # Allow self, inline styles (needed for MUI), and Google reCAPTCHA
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.google.com https://www.gstatic.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "frame-src 'self' https://www.google.com",
            "connect-src 'self' http://localhost:* https://www.google.com",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking (except for admin which may need iframes)
        if not request.path.startswith('/admin/'):
            response['X-Frame-Options'] = 'DENY'
        
        # HSTS - only in production with HTTPS
        if settings.ENVIRONMENT == 'prod':
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Referrer policy - send origin only for cross-origin requests
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy - disable unnecessary browser features
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response


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
            logger.exception(
                "Unhandled exception on path=%s", request.path, exc_info=e
            )
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("home")  # Safe fallback page

    def handle_validation_error(self, request, exception):
        """Log ValidationError details appropriately based on DEBUG setting."""
        user = getattr(request, "user", None)
        participant = getattr(user, "participant", None)

        if settings.DEBUG:
            logger.error(
                "ValidationError on path=%s, user=%s, participant=%s, error=%s",
                request.path, user, participant, exception
            )
        else:
            OrderValidationLog.objects.create(  # pylint: disable=no-member
                user=user if user and user.is_authenticated else None,
                participant=participant,
                message=str(exception),
                log_type=OrderValidationLog.ERROR,
            )
