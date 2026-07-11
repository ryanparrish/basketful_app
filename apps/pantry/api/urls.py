"""
URL configuration for the Pantry API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.pantry.api.views import (
    CategoryViewSet,
    SubcategoryViewSet,
    TagViewSet,
    ProductViewSet,
    ProductLimitViewSet,
    OrderPackerViewSet,
    LowInventoryAlertSettingsViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubcategoryViewSet, basename='subcategory')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-limits', ProductLimitViewSet, basename='product-limit')
router.register(r'order-packers', OrderPackerViewSet, basename='order-packer')
router.register(
    r'low-inventory-alert-settings',
    LowInventoryAlertSettingsViewSet,
    basename='low-inventory-alert-settings',
)

urlpatterns = [
    path('', include(router.urls)),
]
