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
        """
        Safe methods (GET/HEAD/OPTIONS) are public — the login page needs
        program config before a token exists.  All mutations require a
        logged-in admin.
        """
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [AllowAny()]
        return [IsAuthenticated(), IsSingletonAdmin()]

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = ProgramSettings.get_settings()
        if request.method == 'GET':
            serializer = ProgramSettingsSerializer(settings_obj)
            return Response(serializer.data)

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
        """
        Safe methods are public — the login page needs branding before
        a token exists.  All mutations require a logged-in admin.
        """
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [AllowAny()]
        return [IsAuthenticated(), IsSingletonAdmin()]

    @action(detail=False, methods=['get', 'put', 'patch'])
    def current(self, request):
        """Get or update the current settings."""
        settings_obj = ThemeSettings.get_settings()
        if request.method == 'GET':
            serializer = ThemeSettingsSerializer(settings_obj, context={'request': request})
            return Response(serializer.data)

        serializer = ThemeSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=(request.method == 'PATCH'),
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RulesVersionViewSet(viewsets.ViewSet):
    """ViewSet for retrieving current rules version hash."""
    permission_classes = [AllowAny]

    def list(self, request):
        """
        Return the current rules version hash.

        On a cache miss we recompute the hash directly from the DB — no
        model.save() / signal firing needed, so this stays a pure read.
        The freshly computed value is written back to the cache so the
        next caller gets a hit.
        """
        from core.signals import _compute_rules_hash, RULES_VERSION_CACHE_KEY, RULES_VERSION_TTL

        rules_version = cache.get(RULES_VERSION_CACHE_KEY)
        if not rules_version:
            rules_version = _compute_rules_hash()
            if rules_version:
                cache.set(RULES_VERSION_CACHE_KEY, rules_version, timeout=RULES_VERSION_TTL)

        return Response({'rules_version': rules_version or 'unknown'})


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
        from core.utils import get_program_window_status

        # Single query: resolve participant + program together
        from apps.account.models import Participant
        try:
            participant = (
                Participant.objects
                .select_related('program')
                .get(user=request.user)
            )
        except Participant.DoesNotExist:
            return Response(
                {'detail': 'No participant profile linked to this account.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        program = getattr(participant, 'program', None)
        if program is None:
            # No program assigned — fall back to global OrderWindowSettings
            global_s = OrderWindowSettings.get_settings()
            is_open = global_s.enabled
            return Response({
                'is_open': is_open,
                'window_status': 'open' if is_open else 'disabled',
                'seconds_until_change': None,
                'next_opens_at': None,
                'next_closes_at': None,
                'program_name': None,
                'override_reason': None,
            })

        ws = get_program_window_status(program)

        # Pull next open/close times from the first upcoming cycle.
        # Use .get() throughout — defensive against any future shape change.
        cycles = ws.get('cycles') or []
        next_opens_at = None
        next_closes_at = None
        if cycles:
            c = cycles[0]
            opens = c.get('opens_at')
            closes = c.get('closes_at')
            next_opens_at = opens.isoformat() if opens else None
            next_closes_at = closes.isoformat() if closes else None

        window_status = ws.get('window_status', 'disabled')
        is_open = window_status in ('open', 'force_open')

        override = ws.get('override')
        override_reason = override.reason if override else None

        return Response({
            'is_open': is_open,
            'window_status': window_status,
            'seconds_until_change': ws.get('seconds_until_change'),
            'next_opens_at': next_opens_at,
            'next_closes_at': next_closes_at,
            'program_name': program.name,
            'override_reason': override_reason,
        })
