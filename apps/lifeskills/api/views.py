"""
ViewSets for the Lifeskills app.
"""
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from apps.api.pagination import StandardResultsSetPagination
from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser
from apps.lifeskills.models import Program, LifeskillsCoach, ProgramPause
from apps.lifeskills.api.serializers import (
    ProgramSerializer,
    ProgramListSerializer,
    LifeskillsCoachSerializer,
    ProgramPauseSerializer,
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

    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """Return participants for this program."""
        from apps.account.api.serializers import ParticipantSerializer
        program = self.get_object()
        participants = program.participants.all()
        page = self.paginate_queryset(participants)
        if page is not None:
            serializer = ParticipantSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ParticipantSerializer(participants, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def orders(self, request, pk=None):
        """Return orders for this program."""
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


class LifeskillsCoachViewSet(viewsets.ModelViewSet):
    """ViewSet for LifeskillsCoach model."""
    queryset = LifeskillsCoach.objects.all()
    serializer_class = LifeskillsCoachSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'email']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


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
