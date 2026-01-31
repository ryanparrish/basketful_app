"""
URL configuration for the Voucher API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.voucher.api.views import (
    VoucherViewSet,
    VoucherSettingViewSet,
    OrderVoucherViewSet,
)

router = DefaultRouter()
router.register(r'vouchers', VoucherViewSet, basename='voucher')
router.register(r'voucher-settings', VoucherSettingViewSet, basename='voucher-setting')
router.register(r'order-vouchers', OrderVoucherViewSet, basename='order-voucher')

urlpatterns = [
    path('', include(router.urls)),
]
