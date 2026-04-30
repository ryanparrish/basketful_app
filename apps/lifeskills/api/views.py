"""
ViewSets for the Lifeskills app.
"""
from datetime import timedelta

from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser, IsCoachOrStaff
from apps.lifeskills.models import Program, LifeskillsCoach, ProgramPause
from apps.lifeskills.api.serializers import (
    ProgramSerializer,
    ProgramListSerializer,
    LifeskillsCoachSerializer,
    ProgramPauseSerializer,
)
from core.models import ProgramOrderWindow, ProgramWindowOverride
from core.api.serializers import (
    ProgramOrderWindowSerializer,
    ProgramWindowOverrideSerializer,
    ProgramWindowStatusSerializer,
)


class ProgramViewSet(viewsets.ModelViewSet):
    """ViewSet for Program model."""
    queryset = Program.objects.all().prefetch_related('participant_set')
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'meeting_address']
    ordering_fields = ['name', 'MeetingDay', 'created_at']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProgramListSerializer
        return ProgramSerializer

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsStaffUser])
    def participants(self, request, pk=None):
        """Return participants for this program (staff only)."""
        from apps.account.api.serializers import ParticipantSerializer
        program = self.get_object()
        participants = program.participants.all()
        page = self.paginate_queryset(participants)
        if page is not None:
            serializer = ParticipantSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ParticipantSerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsStaffUser])
    def orders(self, request, pk=None):
        """Return orders for this program (staff only)."""
        from apps.orders.api.serializers import OrderListSerializer
        from apps.orders.models import Order
        program = self.get_object()
        orders = Order.objects.filter(
            account__participant__program=program
        ).order_by('-order_date')
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = OrderListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'put', 'delete'], url_path='order-window')
    def order_window(self, request, pk=None):
        """
        GET    /programs/{id}/order-window/  — return effective config + sources
        PUT    /programs/{id}/order-window/  — upsert sparse override
        DELETE /programs/{id}/order-window/  — revert to global defaults
        """
        program = self.get_object()

        if request.method == 'GET':
            from core.utils import get_program_window_status
            status_data = get_program_window_status(program)
            serializer = ProgramWindowStatusSerializer(status_data)
            return Response(serializer.data)

        if request.method == 'DELETE':
            try:
                program.order_window.delete()
            except ProgramOrderWindow.DoesNotExist:
                pass
            return Response(status=status.HTTP_204_NO_CONTENT)

        # PUT — upsert the sparse override row
        try:
            ow = program.order_window
        except ProgramOrderWindow.DoesNotExist:
            ow = ProgramOrderWindow(program=program)

        serializer = ProgramOrderWindowSerializer(ow, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=['post', 'delete'], url_path='order-window/override')
    def window_override(self, request, pk=None):
        """
        POST   /programs/{id}/order-window/override/  — upsert a force-open/close
        DELETE /programs/{id}/order-window/override/  — clear the override early
        """
        program = self.get_object()

        if request.method == 'DELETE':
            try:
                program.window_override.delete()
            except ProgramWindowOverride.DoesNotExist:
                pass
            return Response(status=status.HTTP_204_NO_CONTENT)

        # POST — validate and upsert
        force_status_val = request.data.get('force_status')
        expires_at = request.data.get('expires_at')
        reason = request.data.get('reason', '')

        if force_status_val not in ('open', 'closed'):
            return Response(
                {'detail': 'force_status must be "open" or "closed".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not expires_at:
            return Response(
                {'detail': 'expires_at is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils.dateparse import parse_datetime
        from django.utils.timezone import make_aware, is_naive
        expires_dt = parse_datetime(expires_at)
        if expires_dt and is_naive(expires_dt):
            # datetime-local inputs send naive datetimes (no tz offset); treat as local time
            expires_dt = make_aware(expires_dt)
        if not expires_dt or expires_dt <= timezone.now():
            return Response(
                {'detail': 'expires_at must be a valid datetime in the future.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        override, _ = ProgramWindowOverride.objects.update_or_create(
            program=program,
            defaults={
                'force_status': force_status_val,
                'expires_at': expires_dt,
                'reason': reason,
                'created_by': request.user,
            },
        )
        serializer = ProgramWindowOverrideSerializer(override)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LifeskillsCoachViewSet(viewsets.ModelViewSet):
    """ViewSet for LifeskillsCoach model.

    Staff: full CRUD over all coaches.
    Lifeskills Coach: read/update their own profile only; cannot create or delete.
    """
    serializer_class = LifeskillsCoachSerializer
    permission_classes = [IsAuthenticated, IsCoachOrStaff]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = LifeskillsCoach.objects.select_related('user').prefetch_related('programs').all()
        # Non-staff coaches can only see their own profile
        if (
            not self.request.user.is_staff
            and self.request.user.groups.filter(name='Lifeskills Coach').exists()
        ):
            return qs.filter(user=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff can create coach profiles.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            return Response(
                {'detail': 'Only staff can delete coach profiles.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='my-dashboard')
    def my_dashboard(self, request):
        """
        GET /api/v1/coaches/my-dashboard/

        Returns the authenticated coach's dashboard:
        - Their coach profile
        - Their program's order window status
        - Each assigned participant with recent-order status (last 14 days)
        - Summary counts
        """
        try:
            coach = LifeskillsCoach.objects.prefetch_related('programs').select_related('user').get(
                user=request.user
            )
        except LifeskillsCoach.DoesNotExist:
            return Response(
                {'detail': 'No coach profile found for this user.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        window_status_data = None
        participants_data = []
        summary: dict = {}

        program = coach.programs.first()
        if program:
            from core.utils import get_program_window_status
            window_status_data = get_program_window_status(program)

            from apps.account.models import Participant
            from apps.orders.models import Order

            cutoff = timezone.now() - timedelta(days=14)
            participants = Participant.objects.filter(
                assigned_coach=coach
            ).order_by('name')

            for participant in participants:
                last_order = (
                    Order.objects.filter(
                        account__participant=participant,
                        order_date__gte=cutoff,
                    )
                    .order_by('-order_date')
                    .first()
                )
                participants_data.append({
                    'id': participant.id,
                    'name': participant.name,
                    'customer_number': participant.customer_number,
                    'email': participant.email,
                    'is_active': participant.active,
                    'has_recent_order': last_order is not None,
                    'last_order_date': last_order.order_date if last_order else None,
                    'last_order_id': last_order.id if last_order else None,
                })

            active_count = sum(1 for p in participants_data if p['is_active'])
            orders_placed = sum(
                1 for p in participants_data if p['is_active'] and p['has_recent_order']
            )
            summary = {
                'total_participants': len(participants_data),
                'active_participants': active_count,
                'orders_placed_recently': orders_placed,
                'orders_pending': max(active_count - orders_placed, 0),
            }

        return Response({
            'coach': LifeskillsCoachSerializer(coach, context={'request': request}).data,
            'window_status': window_status_data,
            'participants': participants_data,
            'summary': summary,
        })


class ProgramPauseViewSet(viewsets.ModelViewSet):
    """ViewSet for ProgramPause model."""
    queryset = ProgramPause.objects.all_pauses()
    serializer_class = ProgramPauseSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['pause_start', 'pause_end', 'created_at']
    ordering = ['-pause_start']

    def destroy(self, request, *args, **kwargs):
        """Deletion is disabled — use archive instead."""
        return Response(
            {'detail': 'Deletion is not allowed. Use archive instead.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Return only active pauses."""
        from apps.lifeskills.queryset import program_pause_annotations
        pauses = program_pause_annotations(
            ProgramPause.objects.filter(archived=False)
        ).filter(pause_is_active=True)
        serializer = ProgramPauseSerializer(pauses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Return upcoming pauses (start date in the future)."""
        now = timezone.now()
        pauses = self.get_queryset().filter(pause_start__gt=now)
        page = self.paginate_queryset(pauses)
        if page is not None:
            serializer = ProgramPauseSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ProgramPauseSerializer(pauses, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def check_overlap(self, request):
        """Check if proposed pause dates overlap with existing non-archived pauses."""
        pause_start = request.query_params.get('pause_start')
        pause_end = request.query_params.get('pause_end')
        exclude_id = request.query_params.get('exclude_id')

        if not pause_start or not pause_end:
            return Response(
                {'detail': 'pause_start and pause_end are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from django.utils.dateparse import parse_datetime
            start_dt = parse_datetime(pause_start)
            end_dt = parse_datetime(pause_end)
            if not start_dt or not end_dt:
                return Response(
                    {'detail': 'Invalid datetime format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Invalid datetime format.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = ProgramPause.objects.all_pauses().filter(
            archived=False,
            pause_start__lt=end_dt,
            pause_end__gt=start_dt,
        )
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)

        conflicting = qs.first()
        if conflicting:
            return Response({
                'overlaps': True,
                'conflicting': {
                    'id': conflicting.id,
                    'reason': conflicting.reason,
                    'pause_start': conflicting.pause_start,
                    'pause_end': conflicting.pause_end,
                },
            })
        return Response({'overlaps': False, 'conflicting': None})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive this pause and clean up associated vouchers."""
        pause = self.get_object()
        if pause.archived:
            return Response(
                {'detail': 'Pause is already archived.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        pause.archive()
        serializer = self.get_serializer(pause)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive this pause."""
        pause = self.get_object()
        if not pause.archived:
            return Response(
                {'detail': 'Pause is not archived.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        pause.unarchive()
        serializer = self.get_serializer(pause)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def resync(self, request, pk=None):
        """Emergency manual trigger: force-apply active pause state to vouchers."""
        from apps.voucher.models import Voucher
        from apps.lifeskills.utils import set_voucher_pause_state

        pause = self.get_object()

        if pause.archived:
            return Response(
                {'detail': 'Cannot resync an archived pause.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not pause.is_active_gate:
            return Response(
                {'detail': 'Pause is not currently in the active ordering window.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        voucher_ids = list(
            Voucher.objects.filter(active=True, account__active=True)
            .values_list('id', flat=True)
        )
        updated, skipped = set_voucher_pause_state(
            voucher_ids, activate=True, multiplier=pause.multiplier
        )

        pause.last_resync_at = timezone.now()
        pause.last_resync_by_username = request.user.username
        pause.save(update_fields=['last_resync_at', 'last_resync_by_username'])

        serializer = self.get_serializer(pause)
        return Response({
            **serializer.data,
            'updated_count': updated,
            'skipped_count': skipped,
        })
