"""
Serializers for the Lifeskills app.
"""
from rest_framework import serializers

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
            'multiplier', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LifeskillsCoachSerializer(serializers.ModelSerializer):
    """Serializer for LifeskillsCoach model."""

    class Meta:
        model = LifeskillsCoach
        fields = [
            'id', 'name', 'email', 'phone_number', 'image',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
        return obj.participants.count()

    def get_active_participant_count(self, obj) -> int:
        return obj.participants.filter(active=True).count()


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
        return obj.participants.count()
