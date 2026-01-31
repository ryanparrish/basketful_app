"""
ViewSets for the Account app API.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.models import User

from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser, IsSingletonAdmin
from apps.account.models import (
    UserProfile,
    Participant,
    AccountBalance,
    GoFreshSettings,
)
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    ParticipantSerializer,
    ParticipantCreateSerializer,
    AccountBalanceSerializer,
    GoFreshSettingsSerializer,
    BalanceSummarySerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing User accounts.
    
    list: List all users (staff only)
    retrieve: Get user details
    create: Create a new user (staff only)
    update: Update user (staff only)
    destroy: Delete user (staff only)
    """
    queryset = User.objects.all().select_related('userprofile')
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['username', 'email', 'date_joined', 'last_login']
    ordering = ['-date_joined']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        """Send password reset email to user."""
        user = self.get_object()
        # TODO: Implement password reset email
        return Response({'status': 'password reset email sent'})

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current authenticated user."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class ParticipantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Participants.
    
    Provides full CRUD operations for program participants.
    """
    queryset = Participant.objects.all().select_related(
        'program', 'assigned_coach', 'user'
    )
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['program', 'assigned_coach', 'active']
    search_fields = ['name', 'email', 'customer_number']
    ordering_fields = ['name', 'created_at', 'customer_number']
    ordering = ['name']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ParticipantCreateSerializer
        return ParticipantSerializer

    @action(detail=True, methods=['get'])
    def balances(self, request, pk=None):
        """Get balance summary for a participant."""
        participant = self.get_object()
        balances = participant.balances()
        serializer = BalanceSummarySerializer(balances)
        return Response(serializer.data)


class AccountBalanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AccountBalance.
    
    Provides access to participant account balances with computed properties.
    """
    queryset = AccountBalance.objects.all().select_related('participant')
    serializer_class = AccountBalanceSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['active', 'participant']
    search_fields = ['participant__name', 'participant__customer_number']
    ordering_fields = ['last_updated', 'base_balance']
    ordering = ['-last_updated']


class GoFreshSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GoFreshSettings singleton.
    
    Only one instance exists - use list/retrieve to get settings,
    update/partial_update to modify.
    """
    queryset = GoFreshSettings.objects.all()
    serializer_class = GoFreshSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]

    def get_object(self):
        """Always return the singleton instance."""
        return GoFreshSettings.get_settings()

    def list(self, request, *args, **kwargs):
        """Return the singleton as a single object."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create/update the singleton."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
