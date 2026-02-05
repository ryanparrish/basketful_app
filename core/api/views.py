"""
ViewSets for the Core app.
"""
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache

from apps.api.permissions import IsSingletonAdmin
from core.models import OrderWindowSettings, EmailSettings, BrandingSettings, ProgramSettings, ThemeSettings
from core.api.serializers import (
    OrderWindowSettingsSerializer,
    EmailSettingsSerializer,
    BrandingSettingsSerializer,
    ProgramSettingsSerializer,
    ThemeSettingsSerializer,
)


class OrderWindowSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for OrderWindowSettings singleton model."""
    queryset = OrderWindowSettings.objects.all()
    serializer_class = OrderWindowSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]
    pagination_class = None  # Singleton

    def get_permissions(self):
        """Allow unauthenticated GET requests for order window status."""
        if self.action in ['list', 'retrieve', 'current']:
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = OrderWindowSettings.get_settings()
        if request.method == 'GET':
            serializer = OrderWindowSettingsSerializer(settings_obj, context={'request': request})
            return Response(serializer.data)
        
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


class ProgramSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for ProgramSettings singleton model with public read access."""
    queryset = ProgramSettings.objects.all()
    serializer_class = ProgramSettingsSerializer
    pagination_class = None  # Singleton
    
    def get_permissions(self):
        """Allow unauthenticated GET requests for program config (needed for login page)."""
        if self.action in ['list', 'retrieve', 'current']:
            return [AllowAny()]
        return [IsAuthenticated(), IsSingletonAdmin()]
    
    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[AllowAny])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = ProgramSettings.get_settings()
        if request.method == 'GET':
            serializer = ProgramSettingsSerializer(settings_obj)
            return Response(serializer.data)
        
        # Require admin permissions for updates
        self.permission_classes = [IsAuthenticated, IsSingletonAdmin]
        self.check_permissions(request)
        
        serializer = ProgramSettingsSerializer(
            settings_obj, data=request.data, partial=(request.method == 'PATCH')
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ThemeSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for ThemeSettings singleton model with public read access."""
    queryset = ThemeSettings.objects.all()
    serializer_class = ThemeSettingsSerializer
    pagination_class = None  # Singleton
    
    def get_permissions(self):
        """Allow unauthenticated GET requests for theme config (needed for login page branding)."""
        if self.action in ['list', 'retrieve', 'current']:
            return [AllowAny()]
        return [IsAuthenticated(), IsSingletonAdmin()]
    
    @action(detail=False, methods=['get', 'put', 'patch'], permission_classes=[AllowAny])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = ThemeSettings.get_settings()
        if request.method == 'GET':
            serializer = ThemeSettingsSerializer(settings_obj, context={'request': request})
            return Response(serializer.data)
        
        # Require admin permissions for updates
        self.permission_classes = [IsAuthenticated, IsSingletonAdmin]
        self.check_permissions(request)
        
        serializer = ThemeSettingsSerializer(
            settings_obj, data=request.data, partial=(request.method == 'PATCH'), context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RulesVersionViewSet(viewsets.ViewSet):
    """ViewSet for retrieving current rules version hash."""
    permission_classes = [AllowAny]
    
    def list(self, request):
        """Get current rules version hash from Redis cache."""
        rules_version = cache.get('rules_version')
        if not rules_version:
            # If cache is empty, trigger regeneration
            from core.models import ProgramSettings
            program_settings = ProgramSettings.get_settings()
            # Signal will regenerate hash
            program_settings.save()
            rules_version = cache.get('rules_version', 'unknown')
        
        return Response({'rules_version': rules_version})
