"""
Custom JWT Authentication with httpOnly cookie support.
"""
from django.conf import settings
from django.utils import translation
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that reads tokens from httpOnly cookies.

    Falls back to Authorization header for backwards compatibility.

    Cookie names are configured in settings.SIMPLE_JWT:
    - AUTH_COOKIE: Access token cookie name (default: 'access_token')
    - AUTH_COOKIE_REFRESH: Refresh token cookie name (default: 'refresh_token')

    As the sole configured DRF authentication class, this is also the single
    choke point where the authenticated participant's preferred_language is
    activated for the request. DRF authenticates inside APIView.initial(),
    before the handler runs, so validation errors, serializer output, and
    translated model fields all render in the participant's language.
    A plain Django middleware can't do this — it runs before DRF auth and
    never sees the JWT user.
    """

    def authenticate(self, request):
        result = self._authenticate_token(request)
        if result:
            self._activate_user_language(result[0])
        return result

    def _authenticate_token(self, request):
        # First try to get token from httpOnly cookie
        access_token = request.COOKIES.get(
            settings.SIMPLE_JWT.get('AUTH_COOKIE', 'access_token')
        )

        if access_token:
            # Validate the token from cookie
            try:
                validated_token = self.get_validated_token(access_token)
                return self.get_user(validated_token), validated_token
            except (InvalidToken, TokenError):
                # Cookie token invalid, try header authentication
                pass

        # Fall back to header-based authentication
        return super().authenticate(request)

    @staticmethod
    def _activate_user_language(user):
        """Serve staff in English; participants in their saved language."""
        if user.is_staff:
            translation.activate('en')
            return
        participant = getattr(user, 'participant', None)
        preferred_language = getattr(participant, 'preferred_language', None)
        if preferred_language:
            translation.activate(preferred_language)


class LoginRateThrottle:
    """
    Custom throttle class for login endpoints.
    More restrictive than default anonymous rate.
    """
    from rest_framework.throttling import AnonRateThrottle
    
    class LoginThrottle(AnonRateThrottle):
        rate = '5/minute'
        scope = 'login'
