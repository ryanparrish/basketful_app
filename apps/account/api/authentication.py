"""
Custom JWT Authentication with httpOnly cookie support.
"""
from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that reads tokens from httpOnly cookies.
    
    Falls back to Authorization header for backwards compatibility.
    
    Cookie names are configured in settings.SIMPLE_JWT:
    - AUTH_COOKIE: Access token cookie name (default: 'access_token')
    - AUTH_COOKIE_REFRESH: Refresh token cookie name (default: 'refresh_token')
    """
    
    def authenticate(self, request):
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


class LoginRateThrottle:
    """
    Custom throttle class for login endpoints.
    More restrictive than default anonymous rate.
    """
    from rest_framework.throttling import AnonRateThrottle
    
    class LoginThrottle(AnonRateThrottle):
        rate = '5/minute'
        scope = 'login'
