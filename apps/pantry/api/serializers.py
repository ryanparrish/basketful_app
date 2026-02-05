"""
Serializers for the Pantry app.
"""
from rest_framework import serializers

from apps.pantry.models import (
    Category,
    Subcategory,
    Tag,
    Product,
    ProductLimit,
)


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""

    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubcategorySerializer(serializers.ModelSerializer):
    """Serializer for Subcategory model."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Subcategory
        fields = ['id', 'name', 'category', 'category_name']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    subcategories = SubcategorySerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'subcategories', 'product_count']
        read_only_fields = ['id']

    def get_product_count(self, obj):
        return obj.products.filter(active=True).count()


class CategoryListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Category list views."""

    class Meta:
        model = Category
        fields = ['id', 'name']
        read_only_fields = ['id']


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(
        source='subcategory.name', read_only=True
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        write_only=True,
        source='tags',
        required=False
    )
    limit = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price',
            'category', 'category_name', 'subcategory', 'subcategory_name',
            'quantity_in_stock', 'is_meat', 'weight_lbs',
            'image', 'active', 'tags', 'tag_ids', 'limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_limit(self, obj):
        return Product.get_limit_for_product(obj)


class ProductListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Product list views."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'price', 'category', 'category_name',
            'image', 'active', 'quantity_in_stock'
        ]
        read_only_fields = ['id']


class ProductLimitSerializer(serializers.ModelSerializer):
    """Serializer for ProductLimit model."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(
        source='subcategory.name', read_only=True
    )

    class Meta:
        model = ProductLimit
        fields = [
            'id', 'name', 'category', 'category_name',
            'subcategory', 'subcategory_name', 'limit', 'limit_scope', 'notes'
        ]
        read_only_fields = ['id']
