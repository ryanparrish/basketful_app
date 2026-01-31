"""
ViewSets for the Pantry app.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser
from apps.pantry.models import (
    Category,
    Subcategory,
    Tag,
    Product,
    ProductLimit,
)
from apps.pantry.api.serializers import (
    CategorySerializer,
    CategoryListSerializer,
    SubcategorySerializer,
    TagSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductLimitSerializer,
)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category model."""
    queryset = Category.objects.all().prefetch_related('subcategories')
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name', 'id']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return CategoryListSerializer
        return CategorySerializer


class SubcategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Subcategory model."""
    queryset = Subcategory.objects.all().select_related('category')
    serializer_class = SubcategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['category']
    search_fields = ['name']
    ordering_fields = ['name', 'category__name']
    ordering = ['name']


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet for Tag model."""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product model."""
    queryset = Product.objects.all().select_related(
        'category', 'subcategory'
    ).prefetch_related('tags')
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['category', 'subcategory', 'active', 'is_meat']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at', 'category__name']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return only active products."""
        products = self.queryset.filter(active=True)
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = ProductListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """Return products grouped by category."""
        categories = Category.objects.all().prefetch_related(
            'products__subcategory', 'products__tags'
        )
        result = []
        for category in categories:
            products = category.products.filter(active=True)
            result.append({
                'category': CategoryListSerializer(category).data,
                'products': ProductListSerializer(products, many=True).data
            })
        return Response(result)


class ProductLimitViewSet(viewsets.ModelViewSet):
    """ViewSet for ProductLimit model."""
    queryset = ProductLimit.objects.all().select_related('category', 'subcategory')
    serializer_class = ProductLimitSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [
        DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter
    ]
    filterset_fields = ['category', 'subcategory']
    search_fields = ['name', 'notes']
    ordering_fields = ['name', 'limit']
    ordering = ['name']
