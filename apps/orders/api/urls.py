"""
URL configuration for the Orders API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.orders.api.views import (
    OrderViewSet,
    OrderItemViewSet,
    OrderValidationLogViewSet,
    CombinedOrderViewSet,
    PackingSplitRuleViewSet,
    PackingListViewSet,
)

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='order-item')
router.register(
    r'validation-logs', OrderValidationLogViewSet, basename='validation-log'
)
router.register(r'combined-orders', CombinedOrderViewSet, basename='combined-order')
router.register(
    r'packing-split-rules', PackingSplitRuleViewSet, basename='packing-split-rule'
)
router.register(r'packing-lists', PackingListViewSet, basename='packing-list')

urlpatterns = [
    path('', include(router.urls)),
]
