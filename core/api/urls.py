"""
URL configuration for the Core API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from core.api.views import (
    OrderWindowSettingsViewSet,
    EmailSettingsViewSet,
    BrandingSettingsViewSet,
)

router = DefaultRouter()
router.register(
    r'order-window-settings',
    OrderWindowSettingsViewSet,
    basename='order-window-setting'
)
router.register(
    r'email-settings', EmailSettingsViewSet, basename='email-setting'
)
router.register(
    r'branding-settings', BrandingSettingsViewSet, basename='branding-setting'
)

urlpatterns = [
    path('settings/', include(router.urls)),
]
