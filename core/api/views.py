"""
ViewSets for the Core app.
"""
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.cache import cache
from django.utils import timezone

from apps.api.permissions import IsSingletonAdmin, IsStaffUser
from core.models import (
    OrderWindowSettings,
    EmailSettings,
    BrandingSettings,
    ProgramSettings,
    ThemeSettings,
    ProgramOrderWindow,
    ProgramWindowOverride,
)
from core.api.serializers import (
    OrderWindowSettingsSerializer,
    EmailSettingsSerializer,
    BrandingSettingsSerializer,
    ProgramSettingsSerializer,
    ThemeSettingsSerializer,
    ProgramWindowStatusSerializer,
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


class OrderWindowDashboardView(APIView):
    """
    GET /api/v1/order-windows/status/

    Returns the computed order-window status for every program, plus the
    current global OrderWindowSettings.  Designed to be polled every 30 s
    by the React-Admin dashboard.

    All state is derived on the fly — nothing is written.
    Uses select_related to avoid N+1 queries across programs.
    """
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get(self, request):
        from apps.lifeskills.models import Program
        from core.utils import get_program_window_status

        programs = Program.objects.select_related(
            'order_window',
            'window_override',
            'window_override__created_by',
        ).all()

        statuses = [get_program_window_status(p) for p in programs]
        serializer = ProgramWindowStatusSerializer(statuses, many=True)

        global_settings = OrderWindowSettings.get_settings()
        global_serializer = OrderWindowSettingsSerializer(
            global_settings, context={'request': request}
        )

        return Response({
            'programs': serializer.data,
            'global': global_serializer.data,
            'as_of': timezone.now().isoformat(),
        })


class MyWindowView(APIView):
    """
    GET /api/v1/settings/my-window/

    Returns the order-window status for the authenticated participant's
    own program.  Used by the participant frontend to decide whether
    checkout is available.

    Response shape:
        {
          is_open: bool,
          window_status: str,          # open|closed|force_open|force_closed|disabled|no_schedule
          seconds_until_change: int|null,
          next_opens_at: str|null,     # ISO-8601 aware datetime
          next_closes_at: str|null,
          program_name: str,
          override_reason: str|null,
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.utils import get_program_window_status, generate_window_cycles, get_effective_config

        user = request.user
        # Resolve participant → program
        try:
            participant = user.participant
        except Exception:
            return Response(
                {'detail': 'No participant profile linked to this account.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        program = getattr(participant, 'program', None)
        if program is None:
            return Response(
                {'detail': 'Participant has no program assigned.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        ws = get_program_window_status(program)
        config = get_effective_config(program)

        # Pull next open/close times from the first upcoming cycle
        cycles = ws.get('cycles', [])
        next_opens_at = None
        next_closes_at = None
        if cycles:
            c = cycles[0]
            # c values are datetime objects from generate_window_cycles
            next_opens_at = c['opens_at'].isoformat() if c['opens_at'] else None
            next_closes_at = c['closes_at'].isoformat() if c['closes_at'] else None

        is_open = ws['window_status'] in ('open', 'force_open')

        override = ws.get('override')
        override_reason = None
        if override:
            override_reason = getattr(override, 'reason', None) or None

        return Response({
            'is_open': is_open,
            'window_status': ws['window_status'],
            'seconds_until_change': ws.get('seconds_until_change'),
            'next_opens_at': next_opens_at,
            'next_closes_at': next_closes_at,
            'program_name': program.name,
            'override_reason': override_reason,
        })
