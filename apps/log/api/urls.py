"""
URL configuration for the Log API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.log.api.views import (
    EmailTypeViewSet,
    EmailLogViewSet,
    VoucherLogViewSet,
    OrderValidationLogViewSet,
    UserLoginLogViewSet,
)

router = DefaultRouter()
router.register(r'email-types', EmailTypeViewSet, basename='email-type')
router.register(r'email-logs', EmailLogViewSet, basename='email-log')
router.register(r'voucher-logs', VoucherLogViewSet, basename='voucher-log')
router.register(
    r'order-validation-logs',
    OrderValidationLogViewSet,
    basename='order-validation-log'
)
router.register(r'login-logs', UserLoginLogViewSet, basename='login-log')

urlpatterns = [
    path('', include(router.urls)),
]
