"""
URL patterns for Account API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet,
    GroupViewSet,
    PermissionViewSet,
    ParticipantViewSet,
    AccountBalanceViewSet,
    GoFreshSettingsViewSet,
    HygieneSettingsViewSet,
)
from .auth_views import (
    CookieTokenObtainView,
    CookieTokenRefreshView,
    CookieTokenLogoutView,
    AuthMeView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'participants', ParticipantViewSet, basename='participant')
router.register(r'account-balances', AccountBalanceViewSet, basename='accountbalance')
router.register(r'go-fresh-settings', GoFreshSettingsViewSet, basename='gofreshsettings')
router.register(r'hygiene-settings', HygieneSettingsViewSet, basename='hygienesettings')

urlpatterns = [
    # Cookie-based auth endpoints
    path('auth/login/', CookieTokenObtainView.as_view(), name='auth_login'),
    path('auth/refresh/', CookieTokenRefreshView.as_view(), name='auth_refresh'),
    path('auth/logout/', CookieTokenLogoutView.as_view(), name='auth_logout'),
    path('auth/me/', AuthMeView.as_view(), name='auth_me'),
    
    # ViewSet routes
    path('', include(router.urls)),
]
