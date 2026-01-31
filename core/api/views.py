"""
ViewSets for the Core app.
"""
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.api.permissions import IsSingletonAdmin
from core.models import OrderWindowSettings, EmailSettings, BrandingSettings
from core.api.serializers import (
    OrderWindowSettingsSerializer,
    EmailSettingsSerializer,
    BrandingSettingsSerializer,
)


class OrderWindowSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for OrderWindowSettings singleton model."""
    queryset = OrderWindowSettings.objects.all()
    serializer_class = OrderWindowSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]
    pagination_class = None  # Singleton

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = OrderWindowSettings.get_settings()
        if request.method == 'GET':
            return Response(OrderWindowSettingsSerializer(settings_obj).data)
        
        serializer = OrderWindowSettingsSerializer(
            settings_obj, data=request.data, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class EmailSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for EmailSettings singleton model."""
    queryset = EmailSettings.objects.all()
    serializer_class = EmailSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]
    pagination_class = None  # Singleton

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = EmailSettings.get_settings()
        if request.method == 'GET':
            return Response(EmailSettingsSerializer(settings_obj).data)
        
        serializer = EmailSettingsSerializer(
            settings_obj, data=request.data, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BrandingSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for BrandingSettings singleton model."""
    queryset = BrandingSettings.objects.all()
    serializer_class = BrandingSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]
    pagination_class = None  # Singleton

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = BrandingSettings.get_settings()
        if request.method == 'GET':
            return Response(BrandingSettingsSerializer(settings_obj).data)
        
        serializer = BrandingSettingsSerializer(
            settings_obj, data=request.data, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
