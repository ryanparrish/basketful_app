"""
Cookie-based JWT authentication views.

These views set JWT tokens as httpOnly cookies instead of returning them
in the response body for enhanced security against XSS attacks.
"""
import logging

from django.conf import settings
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
import requests

from .jwt_serializers import FlexibleTokenObtainPairSerializer
from .serializers import ParticipantSerializer
from apps.account.models import Participant

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    """Stricter rate limiting for login attempts."""
    rate = '5/minute'
    scope = 'login'


# H7: reuse-grace window for refresh-token rotation. When the server rotates
# a refresh token but the client never receives the new cookies (two tabs
# refreshing at once, or a retry after a network blip), the client presents
# the already-blacklisted old token. Honoring it within this window keeps
# the session alive instead of 401ing with a misleading "Session expired".
REFRESH_REUSE_GRACE_SECONDS = 60


def _user_from_recently_rotated_token(raw_token):
    """Return the user if raw_token is a refresh token blacklisted within the
    reuse-grace window (i.e. the server rotated it moments ago but the client
    never got the new cookies); otherwise None.

    Only honors tokens that still verify (signature + expiry) — malformed or
    genuinely expired tokens get no grace.
    """
    from django.utils import timezone
    from rest_framework_simplejwt.settings import api_settings
    from rest_framework_simplejwt.tokens import UntypedToken
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

    try:
        untoken = UntypedToken(raw_token)
    except TokenError:
        return None
    jti = untoken.get('jti')
    user_id = untoken.get(api_settings.USER_ID_CLAIM)
    if not jti or not user_id:
        return None
    try:
        blacklisted = BlacklistedToken.objects.select_related('token').get(
            token__jti=jti
        )
    except BlacklistedToken.DoesNotExist:
        return None
    age = (timezone.now() - blacklisted.blacklisted_at).total_seconds()
    if age > REFRESH_REUSE_GRACE_SECONDS:
        return None
    from django.contrib.auth.models import User
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


def get_cookie_settings():
    """Get cookie settings from Django settings."""
    jwt_settings = settings.SIMPLE_JWT
    return {
        'httponly': jwt_settings.get('AUTH_COOKIE_HTTP_ONLY', True),
        'secure': jwt_settings.get('AUTH_COOKIE_SECURE', settings.AUTH_COOKIE_SECURE),
        'samesite': jwt_settings.get('AUTH_COOKIE_SAMESITE', settings.AUTH_COOKIE_SAMESITE),
        'path': jwt_settings.get('AUTH_COOKIE_PATH', '/'),
    }


def set_token_cookies(response, access_token, refresh_token=None):
    """Set JWT tokens as httpOnly cookies on response."""
    jwt_settings = settings.SIMPLE_JWT
    cookie_settings = get_cookie_settings()
    
    # Set access token cookie
    response.set_cookie(
        key=jwt_settings.get('AUTH_COOKIE', 'access_token'),
        value=str(access_token),
        max_age=int(jwt_settings['ACCESS_TOKEN_LIFETIME'].total_seconds()),
        **cookie_settings
    )
    
    # Set refresh token cookie if provided
    if refresh_token:
        response.set_cookie(
            key=jwt_settings.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
            value=str(refresh_token),
            max_age=int(jwt_settings['REFRESH_TOKEN_LIFETIME'].total_seconds()),
            **cookie_settings
        )
    
    return response


def clear_token_cookies(response):
    """Clear JWT token cookies."""
    jwt_settings = settings.SIMPLE_JWT
    cookie_settings = get_cookie_settings()
    
    response.delete_cookie(
        key=jwt_settings.get('AUTH_COOKIE', 'access_token'),
        path=cookie_settings['path'],
        samesite=cookie_settings['samesite'],
    )
    response.delete_cookie(
        key=jwt_settings.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
        path=cookie_settings['path'],
        samesite=cookie_settings['samesite'],
    )
    
    return response


def verify_recaptcha(token, action=None):
    """
    Verify reCAPTCHA v2 token with Google.
    
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not token:
        return False, 'reCAPTCHA token is required'
    
    secret_key = settings.RECAPTCHA_PRIVATE_KEY
    
    # Skip verification if using test keys
    if secret_key == 'test-private-key':
        return True, None
    
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': secret_key,
                'response': token,
            },
            timeout=5
        )
        result = response.json()
        
        if result.get('success'):
            return True, None
        else:
            errors = result.get('error-codes', ['unknown-error'])
            return False, f'reCAPTCHA verification failed: {", ".join(errors)}'
            
    except requests.RequestException:
        # Log internally; never surface connection details to the caller
        logger.exception("reCAPTCHA verification request failed")
        return False, 'reCAPTCHA verification is temporarily unavailable. Please try again.'


class CookieTokenObtainView(APIView):
    """
    Login endpoint that sets JWT tokens as httpOnly cookies.
    
    Requires reCAPTCHA v2 verification for security.
    
    POST /api/auth/login/
    {
        "username": "customer_number_or_username",
        "password": "password",
        "recaptcha_token": "token_from_recaptcha_widget"
    }
    
    Response:
    - Sets access_token and refresh_token as httpOnly cookies
    - Returns user info in response body
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    
    def post(self, request):
        # Verify reCAPTCHA
        recaptcha_token = request.data.get('recaptcha_token')
        recaptcha_success, recaptcha_error = verify_recaptcha(recaptcha_token)
        
        if not recaptcha_success:
            return Response(
                {'detail': recaptcha_error, 'code': 'recaptcha_failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate credentials
        serializer = FlexibleTokenObtainPairSerializer(data={
            'username': request.data.get('username', ''),
            'password': request.data.get('password', ''),
        })
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            # Return authentication errors
            error_detail = getattr(e, 'detail', str(e))
            return Response(
                error_detail if isinstance(error_detail, dict) else {'detail': str(error_detail)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get tokens from serializer (it generates them internally)
        validated_data = serializer.validated_data
        access_token = validated_data.get('access')
        refresh_token = validated_data.get('refresh')
        user_data = validated_data.get('user', {})
        
        # Create response with user data
        response = Response({
            'user': user_data,
            'message': 'Login successful',
        })
        
        # Set tokens as httpOnly cookies
        set_token_cookies(response, access_token, refresh_token)
        
        # Ensure CSRF token is set
        get_token(request)
        
        return response


class CookieTokenRefreshView(APIView):
    """
    Refresh endpoint that reads refresh token from cookie.
    
    POST /api/auth/refresh/
    
    Response:
    - Sets new access_token cookie
    - Sets new refresh_token cookie (token rotation)
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    
    def post(self, request):
        jwt_settings = settings.SIMPLE_JWT
        refresh_token = request.COOKIES.get(
            jwt_settings.get('AUTH_COOKIE_REFRESH', 'refresh_token')
        )
        
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token not found', 'code': 'token_not_found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            # Validate and rotate refresh token
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token
            
            # Blacklist old token and get new refresh token
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', True):
                refresh.blacklist()
                # Get the user to create proper token
                from django.contrib.auth.models import User
                try:
                    user = User.objects.get(id=refresh.payload.get('user_id'))
                    new_refresh = RefreshToken.for_user(user)
                except User.DoesNotExist:
                    return Response(
                        {'detail': 'User not found', 'code': 'user_not_found'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            else:
                new_refresh = refresh
            
            # Create response
            response = Response({'message': 'Token refreshed'})
            set_token_cookies(response, str(new_refresh.access_token), str(new_refresh))
            
            return response
            
        except TokenError as e:
            # Rotation race (H7): the client presents a refresh token the
            # server already rotated. If it was blacklisted within the reuse
            # grace window, issue fresh tokens instead of killing the session.
            user = _user_from_recently_rotated_token(refresh_token)
            if user is not None:
                new_refresh = RefreshToken.for_user(user)
                response = Response({'message': 'Token refreshed'})
                set_token_cookies(
                    response, str(new_refresh.access_token), str(new_refresh)
                )
                return response
            return Response(
                {'detail': 'Session expired. Please sign in again.', 'code': 'token_expired'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class CookieTokenLogoutView(APIView):
    """
    Logout endpoint that blacklists refresh token and clears cookies.

    POST /api/auth/logout/

    Deliberately AllowAny (H6): the view body only blacklists the refresh
    cookie and clears cookies — it never uses request.user. Requiring
    IsAuthenticated meant an expired 60-min access token 401'd before the
    body ran, leaving the 7-day refresh cookie alive on shared computers.

    Response:
    - Blacklists the refresh token
    - Clears access_token and refresh_token cookies
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        jwt_settings = settings.SIMPLE_JWT
        refresh_token = request.COOKIES.get(
            jwt_settings.get('AUTH_COOKIE_REFRESH', 'refresh_token')
        )
        
        # Blacklist the refresh token if it exists
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                # Token already invalid, just clear cookies
                pass
        
        # Create response and clear cookies
        response = Response({'message': 'Logged out successfully'})
        clear_token_cookies(response)
        
        return response


class AuthMeView(APIView):
    """
    Get current authenticated user information.
    
    GET /api/auth/me/
    
    Returns user and participant data if authenticated.
    Used by frontend to verify authentication status.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get participant data if exists
        participant_data = None
        try:
            participant = Participant.objects.get(user=user)
            participant_data = ParticipantSerializer(participant).data
        except Participant.DoesNotExist:
            pass
        
        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            },
            'participant': participant_data,
        })
