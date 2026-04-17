"""
Serializers for the Lifeskills app.
"""
from rest_framework import serializers
from django.contrib.auth.models import User

from apps.lifeskills.models import Program, LifeskillsCoach, ProgramPause


class ProgramPauseSerializer(serializers.ModelSerializer):
    """Serializer for ProgramPause model."""
    multiplier = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(
        source='is_active_gate', read_only=True
    )

    class Meta:
        model = ProgramPause
        fields = [
            'id', 'pause_start', 'pause_end', 'reason',
            'multiplier', 'is_active', 'archived', 'archived_at',
            'last_resync_at', 'last_resync_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'archived', 'archived_at',
            'last_resync_at', 'last_resync_by_username',
            'created_at', 'updated_at'
        ]


class LifeskillsCoachSerializer(serializers.ModelSerializer):
    """Serializer for LifeskillsCoach model."""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    program_name = serializers.CharField(source='program.name', read_only=True)

    class Meta:
        model = LifeskillsCoach
        fields = [
            'id', 'name', 'email', 'phone_number', 'image',
            'user', 'user_username', 'user_email',
            'program', 'program_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_username', 'user_email', 'program_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True, 'default': ''},
            'phone_number': {'required': False, 'allow_blank': True, 'default': ''},
            'user': {'required': False, 'allow_null': True},
            'program': {'required': False, 'allow_null': True},
            'image': {'required': False, 'allow_null': True},
        }


class CoachParticipantStatusSerializer(serializers.Serializer):
    """Participant with their recent order status for coach dashboard."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    customer_number = serializers.CharField(allow_null=True)
    email = serializers.EmailField()
    is_active = serializers.BooleanField()
    has_recent_order = serializers.BooleanField()
    last_order_date = serializers.DateTimeField(allow_null=True)
    last_order_id = serializers.IntegerField(allow_null=True)


class CoachDashboardSummarySerializer(serializers.Serializer):
    """Summary counts for the coach dashboard."""
    total_participants = serializers.IntegerField()
    active_participants = serializers.IntegerField()
    orders_placed_recently = serializers.IntegerField()
    orders_pending = serializers.IntegerField()


class ProgramSerializer(serializers.ModelSerializer):
    """Serializer for Program model."""
    participant_count = serializers.SerializerMethodField()
    active_participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            'id', 'name', 'meeting_time', 'MeetingDay', 'meeting_address',
            'default_split_strategy', 'participant_count',
            'active_participant_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_participant_count(self, obj) -> int:
        return obj.participant_set.count()

    def get_active_participant_count(self, obj) -> int:
        return obj.participant_set.filter(active=True).count()


class ProgramListSerializer(serializers.ModelSerializer):
    """Simplified serializer for Program list views."""
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = [
            'id', 'name', 'MeetingDay', 'meeting_time',
            'participant_count', 'default_split_strategy'
        ]
        read_only_fields = ['id']

    def get_participant_count(self, obj) -> int:
        return obj.participant_set.count()
