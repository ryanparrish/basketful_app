"""
ViewSets for the Account app API.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string

from apps.api.permissions import IsAdminOrReadOnly, IsStaffUser, IsSingletonAdmin
from apps.account.models import (
    UserProfile,
    Participant,
    AccountBalance,
    GoFreshSettings,
    HygieneSettings,
)
from apps.account.utils.balance_utils import calculate_base_balance
from apps.account.utils.user_utils import create_participant_user
from apps.account.tasks.email import send_password_reset_email, send_new_user_onboarding_email
from apps.pantry.utils.voucher_utils import setup_account_and_vouchers
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    GroupSerializer,
    PermissionSerializer,
    ParticipantSerializer,
    ParticipantCreateSerializer,
    AccountBalanceSerializer,
    GoFreshSettingsSerializer,
    HygieneSettingsSerializer,
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

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Get current authenticated user."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='me/permissions', permission_classes=[IsAuthenticated])
    def my_permissions(self, request):
        """Get current user's permissions."""
        user = request.user
        permissions = list(user.get_all_permissions()) if not user.is_superuser else ['*']
        groups = list(user.groups.values_list('name', flat=True))
        
        return Response({
            'permissions': permissions,
            'groups': groups,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        })


class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Groups.
    
    Allows staff users to create, view, edit, and delete user groups
    and manage their permissions.
    """
    queryset = Group.objects.all().prefetch_related('permissions')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['name']
    ordering = ['name']


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for Permissions.
    
    Allows staff users to view available permissions for assignment to groups.
    """
    queryset = Permission.objects.all().select_related('content_type')
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['content_type__app_label', 'content_type__model']
    search_fields = ['name', 'codename']
    ordering_fields = ['name', 'codename']
    ordering = ['content_type__app_label', 'content_type__model', 'codename']


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

    @action(detail=False, methods=['get'], url_path='me/balances', permission_classes=[IsAuthenticated])
    def me_balances(self, request):
        """Get balance summary for the current authenticated user's participant."""
        try:
            participant = request.user.participant
            balances = participant.balances()
            serializer = BalanceSummarySerializer(balances)
            return Response(serializer.data)
        except Participant.DoesNotExist:
            return Response(
                {'error': 'No participant profile found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def balances(self, request, pk=None):
        """Get balance summary for a participant."""
        participant = self.get_object()
        balances = participant.balances()
        serializer = BalanceSummarySerializer(balances)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='bulk-calculate-base-balance')
    def bulk_calculate_base_balance(self, request):
        """Calculate and save base balance for selected participants."""
        ids = request.data.get('ids', [])
        updated = 0
        for participant in Participant.objects.filter(id__in=ids):
            base = calculate_base_balance(participant)
            ab, _ = AccountBalance.objects.get_or_create(participant=participant)
            ab.base_balance = base
            ab.save()
            updated += 1
        return Response({'message': f'Base balance calculated for {updated} participant(s).'})

    @action(detail=False, methods=['post'], url_path='bulk-reset-password')
    def bulk_reset_password(self, request):
        """Reset password and queue reset email for selected participants."""
        ids = request.data.get('ids', [])
        reset_count = 0
        skipped = 0
        for participant in Participant.objects.filter(id__in=ids).select_related('user'):
            if not participant.user:
                skipped += 1
                continue
            user = participant.user
            user.password = make_password(get_random_string(length=12))
            user.save(update_fields=['password'])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.must_change_password = True
            profile.save(update_fields=['must_change_password'])
            send_password_reset_email.delay(user.id)
            reset_count += 1
        parts = [f'Password reset for {reset_count} participant(s).']
        if skipped:
            parts.append(f'Skipped {skipped} (no user account).')
        return Response({'message': ' '.join(parts)})

    @action(detail=False, methods=['post'], url_path='bulk-resend-onboarding')
    def bulk_resend_onboarding(self, request):
        """Resend onboarding email to selected participants."""
        ids = request.data.get('ids', [])
        sent, skipped_no_user, skipped_no_email = 0, 0, 0
        for participant in Participant.objects.filter(id__in=ids).select_related('user'):
            if not participant.user:
                skipped_no_user += 1
                continue
            if not participant.user.email:
                skipped_no_email += 1
                continue
            send_new_user_onboarding_email.delay(participant.user.id, force=True)
            sent += 1
        parts = []
        if sent:
            parts.append(f'Queued {sent} onboarding email(s).')
        if skipped_no_user:
            parts.append(f'Skipped {skipped_no_user} (no user account).')
        if skipped_no_email:
            parts.append(f'Skipped {skipped_no_email} (no email address).')
        return Response({'message': ' '.join(parts) or 'No participants selected.'})

    @action(detail=False, methods=['post'], url_path='bulk-resend-password-reset')
    def bulk_resend_password_reset(self, request):
        """Resend password reset email to selected participants."""
        ids = request.data.get('ids', [])
        sent, skipped_no_user, skipped_no_email = 0, 0, 0
        for participant in Participant.objects.filter(id__in=ids).select_related('user'):
            if not participant.user:
                skipped_no_user += 1
                continue
            if not participant.user.email:
                skipped_no_email += 1
                continue
            send_password_reset_email.delay(participant.user.id, force=True)
            sent += 1
        parts = []
        if sent:
            parts.append(f'Queued {sent} password reset email(s).')
        if skipped_no_user:
            parts.append(f'Skipped {skipped_no_user} (no user account).')
        if skipped_no_email:
            parts.append(f'Skipped {skipped_no_email} (no email address).')
        return Response({'message': ' '.join(parts) or 'No participants selected.'})

    def _create_user_for_participant(self, participant, send_email=True):
        """Create a user account for a participant without one."""
        if participant.user:
            return False, 'has_user'
        if not participant.email:
            return False, 'no_email'
        user = create_participant_user(
            first_name=participant.name,
            email=participant.email,
            participant_name=participant.name,
        )
        participant.user = user
        participant.save(update_fields=['user'])
        UserProfile.objects.get_or_create(user=user)
        setup_account_and_vouchers(participant)
        if send_email:
            send_new_user_onboarding_email.delay(user_id=user.id)
        return True, 'created'

    @action(detail=False, methods=['post'], url_path='bulk-create-user-accounts')
    def bulk_create_user_accounts(self, request):
        """Create user accounts for selected participants (with onboarding email)."""
        ids = request.data.get('ids', [])
        created, skipped_has_user, skipped_no_email = 0, 0, 0
        for participant in Participant.objects.filter(id__in=ids).select_related('user'):
            success, reason = self._create_user_for_participant(participant, send_email=True)
            if success:
                created += 1
            elif reason == 'has_user':
                skipped_has_user += 1
            elif reason == 'no_email':
                skipped_no_email += 1
        parts = []
        if created:
            parts.append(f'Created {created} user account(s). Onboarding email(s) queued.')
        if skipped_has_user:
            parts.append(f'Skipped {skipped_has_user} (already have user).')
        if skipped_no_email:
            parts.append(f'Skipped {skipped_no_email} (no email address).')
        return Response({'message': ' '.join(parts) or 'No participants selected.'})

    @action(detail=False, methods=['post'], url_path='bulk-create-user-accounts-silent')
    def bulk_create_user_accounts_silent(self, request):
        """Create user accounts for selected participants (no email)."""
        ids = request.data.get('ids', [])
        created, skipped_has_user, skipped_no_email = 0, 0, 0
        for participant in Participant.objects.filter(id__in=ids).select_related('user'):
            success, reason = self._create_user_for_participant(participant, send_email=False)
            if success:
                created += 1
            elif reason == 'has_user':
                skipped_has_user += 1
            elif reason == 'no_email':
                skipped_no_email += 1
        parts = []
        if created:
            parts.append(f'Created {created} user account(s) (no email sent).')
        if skipped_has_user:
            parts.append(f'Skipped {skipped_has_user} (already have user).')
        if skipped_no_email:
            parts.append(f'Skipped {skipped_no_email} (no email address).')
        return Response({'message': ' '.join(parts) or 'No participants selected.'})


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


class HygieneSettingsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for HygieneSettings singleton.
    
    Only one instance exists - use list/retrieve to get settings,
    update/partial_update to modify.
    """
    queryset = HygieneSettings.objects.all()
    serializer_class = HygieneSettingsSerializer
    permission_classes = [IsAuthenticated, IsSingletonAdmin]

    def get_object(self):
        """Always return the singleton instance."""
        return HygieneSettings.get_settings()

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

