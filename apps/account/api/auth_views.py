"""
Cookie-based JWT authentication views.

These views set JWT tokens as httpOnly cookies instead of returning them
in the response body for enhanced security against XSS attacks.
"""
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


class LoginRateThrottle(AnonRateThrottle):
    """Stricter rate limiting for login attempts."""
    rate = '5/minute'
    scope = 'login'


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
            
    except requests.RequestException as e:
        return False, f'reCAPTCHA verification error: {str(e)}'


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
                new_refresh = RefreshToken.for_user(refresh.payload.get('user_id'))
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
            return Response(
                {'detail': 'Session expired. Please sign in again.', 'code': 'token_expired'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class CookieTokenLogoutView(APIView):
    """
    Logout endpoint that blacklists refresh token and clears cookies.
    
    POST /api/auth/logout/
    
    Response:
    - Blacklists the refresh token
    - Clears access_token and refresh_token cookies
    """
    permission_classes = [IsAuthenticated]
    
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
