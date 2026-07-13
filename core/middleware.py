# core/middleware.py
"""Middleware for global error handling, logging, and security headers."""
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import JsonResponse
from django.middleware.locale import LocaleMiddleware
from django.shortcuts import redirect
from django.utils import translation
from apps.log.models import OrderValidationLog

logger = logging.getLogger("custom_validation")

_IS_PROD = getattr(settings, 'IS_PROD', False)


class StaffAwareLocaleMiddleware(LocaleMiddleware):
    """
    LocaleMiddleware that pins the Django admin to English.

    With 'es' in LANGUAGES, Django's shipped Spanish admin catalog would
    otherwise activate for any staff member whose browser sends a Spanish
    Accept-Language header. Staff surfaces are English-only by design.

    All other requests get standard Accept-Language negotiation — the
    fallback for anonymous participants (login, password reset). For
    authenticated participants the JWT layer overrides this with their
    saved preferred_language (see CookieJWTAuthentication).
    """

    def process_request(self, request):
        if request.path.startswith('/admin/'):
            translation.activate('en')
            request.LANGUAGE_CODE = translation.get_language()
            return
        super().process_request(request)


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
        if _IS_PROD:
            # Production: restrict connect-src to self only (no localhost)
            connect_src = "'self' https://www.google.com https://cloudflareinsights.com"
        else:
            # Development: also allow localhost for hot-reload / dev servers
            connect_src = "'self' http://localhost:* ws://localhost:* https://www.google.com https://cloudflareinsights.com"

        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.google.com https://www.gstatic.com https://static.cloudflareinsights.com",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "frame-src 'self' https://www.google.com",
            f"connect-src {connect_src}",
        ]
        response['Content-Security-Policy'] = '; '.join(csp_directives)
        
        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking (except for admin which may need iframes)
        if not request.path.startswith('/admin/'):
            response['X-Frame-Options'] = 'DENY'
        
        # HSTS - only in production with HTTPS
        if _IS_PROD:
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

        is_api = request.path.startswith("/api/")

        try:
            return self.get_response(request)

        except ValidationError as e:
            self.handle_validation_error(request, e)

            if is_api:
                return JsonResponse(
                    {'detail': str(e)}, status=400
                )

            # For non-API paths → redirect with toast
            if not request.path.startswith("/admin/"):
                messages.error(request, str(e))
                return redirect("participant_dashboard")

            raise

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Unhandled exception on path=%s", request.path, exc_info=e
            )

            if is_api:
                # Return a generic JSON error — never expose internal detail
                return JsonResponse(
                    {'detail': 'An unexpected error occurred. Please try again.'},
                    status=500,
                )

            messages.error(request, "Something went wrong. Please try again.")
            return redirect("home")

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
