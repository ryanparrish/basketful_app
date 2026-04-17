"""
API URL Configuration for Basketful.

All API endpoints are versioned under /api/v1/
"""
from django.conf import settings
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from apps.account.api.jwt_serializers import FlexibleTokenObtainPairSerializer


class FlexibleTokenObtainPairView(TokenObtainPairView):
    """JWT view that accepts customer_number or username for authentication."""
    serializer_class = FlexibleTokenObtainPairSerializer


# Create router for ViewSet registration
router = DefaultRouter()

app_name = 'api'

urlpatterns = [
    # JWT Authentication endpoints
    path('token/', FlexibleTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # App-specific API routes
    path('', include('apps.account.api.urls')),
    path('', include('apps.pantry.api.urls')),
    path('', include('apps.orders.api.urls')),
    path('', include('apps.voucher.api.urls')),
    path('', include('apps.lifeskills.api.urls')),
    path('', include('apps.log.api.urls')),
    path('', include('core.api.urls')),
]

# API docs are only available outside of production to avoid exposing
# a machine-readable endpoint map to unauthenticated attackers.
if not settings.IS_PROD:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularSwaggerView,
        SpectacularRedocView,
    )
    urlpatterns += [
        path('schema/', SpectacularAPIView.as_view(), name='schema'),
        path(
            'docs/',
            SpectacularSwaggerView.as_view(url_name='api:schema'),
            name='swagger-ui'
        ),
        path(
            'redoc/',
            SpectacularRedocView.as_view(url_name='api:schema'),
            name='redoc'
        ),
    ]
