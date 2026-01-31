"""
URL patterns for Account API endpoints.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserViewSet,
    ParticipantViewSet,
    AccountBalanceViewSet,
    GoFreshSettingsViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'participants', ParticipantViewSet, basename='participant')
router.register(r'account-balances', AccountBalanceViewSet, basename='accountbalance')
router.register(r'go-fresh-settings', GoFreshSettingsViewSet, basename='gofreshsettings')

urlpatterns = [
    path('', include(router.urls)),
]
