"""
Serializers for the Account app.
"""
from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType

from apps.account.models import (
    UserProfile,
    Participant,
    AccountBalance,
    GoFreshSettings,
    HygieneSettings,
)


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'must_change_password', 'active']
        read_only_fields = ['id']


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Django Permission model."""
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    model = serializers.CharField(source='content_type.model', read_only=True)
    
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type', 'app_label', 'model']
        read_only_fields = ['id', 'app_label', 'model']


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Django Group model."""
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        required=False
    )
    permission_details = PermissionSerializer(source='permissions', many=True, read_only=True)
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permission_details', 'user_count']
        read_only_fields = ['id', 'user_count']
    
    def get_user_count(self, obj):
        return obj.user_set.count()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for Django User model."""
    profile = UserProfileSerializer(source='userprofile', read_only=True)
    full_name = serializers.SerializerMethodField()
    groups = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Group.objects.all(),
        required=False
    )
    group_details = GroupSerializer(source='groups', many=True, read_only=True)
    user_permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        required=False
    )
    all_permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser', 'date_joined', 'last_login',
            'profile', 'full_name', 'groups', 'group_details',
            'user_permissions', 'all_permissions'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False}
        }

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username
    
    def get_all_permissions(self, obj):
        """Get all permissions (direct + from groups)."""
        if obj.is_superuser:
            return ['*']  # Superuser has all permissions
        return list(obj.get_all_permissions())


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new users."""
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'first_name', 'last_name', 'is_staff']
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        # Create UserProfile
        UserProfile.objects.create(user=user, must_change_password=True)
        return user


class AccountBalanceSerializer(serializers.ModelSerializer):
    """Serializer for AccountBalance with computed balance properties."""
    full_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    available_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    hygiene_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    go_fresh_balance = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    participant_name = serializers.CharField(
        source='participant.name', read_only=True
    )
    customer_number = serializers.CharField(
        source='participant.customer_number', read_only=True
    )

    class Meta:
        model = AccountBalance
        fields = [
            'id', 'participant', 'participant_name', 'customer_number',
            'base_balance', 'full_balance', 'available_balance',
            'hygiene_balance', 'go_fresh_balance',
            'active', 'last_updated', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'full_balance', 'available_balance',
            'hygiene_balance', 'go_fresh_balance', 'last_updated'
        ]


class ParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Participant model."""
    balances = serializers.SerializerMethodField()
    household_size = serializers.SerializerMethodField()
    program_name = serializers.CharField(source='program.name', read_only=True)
    coach_name = serializers.CharField(
        source='assigned_coach.name', read_only=True
    )
    user_username = serializers.CharField(
        source='user.username', read_only=True
    )

    class Meta:
        model = Participant
        fields = [
            'id', 'name', 'email', 'customer_number',
            'adults', 'children', 'diaper_count', 'household_size',
            'program', 'program_name', 'assigned_coach', 'coach_name',
            'user', 'user_username', 'create_user',
            'allergy', 'active', 'balances',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'customer_number', 'created_at', 'updated_at']

    def get_balances(self, obj):
        return obj.balances()

    def get_household_size(self, obj):
        return obj.household_size()


class ParticipantCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating participants."""

    class Meta:
        model = Participant
        fields = [
            'id', 'name', 'email', 'adults', 'children', 'diaper_count',
            'program', 'assigned_coach', 'create_user', 'allergy', 'active'
        ]
        read_only_fields = ['id']


class GoFreshSettingsSerializer(serializers.ModelSerializer):
    """Serializer for GoFreshSettings singleton."""

    class Meta:
        model = GoFreshSettings
        fields = [
            'id', 'small_household_budget', 'medium_household_budget',
            'large_household_budget', 'small_threshold', 'large_threshold',
            'enabled'
        ]
        read_only_fields = ['id']


class HygieneSettingsSerializer(serializers.ModelSerializer):
    """Serializer for HygieneSettings singleton."""

    class Meta:
        model = HygieneSettings
        fields = ['id', 'hygiene_ratio', 'enabled']
        read_only_fields = ['id']


class BalanceSummarySerializer(serializers.Serializer):
    """Serializer for balance summary endpoint."""
    full_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    hygiene_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    go_fresh_balance = serializers.DecimalField(max_digits=10, decimal_places=2)

