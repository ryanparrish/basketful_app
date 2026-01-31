"""
API URL Configuration for Basketful.

All API endpoints are versioned under /api/v1/
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Create router for ViewSet registration
router = DefaultRouter()

# ViewSets will be registered here as they are created
# Example:
# from apps.account.api.views import UserViewSet, ParticipantViewSet
# router.register(r'users', UserViewSet, basename='user')
# router.register(r'participants', ParticipantViewSet, basename='participant')

app_name = 'api'

urlpatterns = [
    # JWT Authentication endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API Documentation
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

    # App-specific API routes
    path('', include('apps.account.api.urls')),
    path('', include('apps.pantry.api.urls')),
    path('', include('apps.orders.api.urls')),
    path('', include('apps.voucher.api.urls')),
    path('', include('apps.lifeskills.api.urls')),
    path('', include('apps.log.api.urls')),
    path('', include('core.api.urls')),
]
