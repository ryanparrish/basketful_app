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
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubcategoryViewSet, basename='subcategory')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-limits', ProductLimitViewSet, basename='product-limit')

urlpatterns = [
    path('', include(router.urls)),
]
