from django.db import models
from django.utils import timezone



class ProgramPauseQuerySet(models.QuerySet):
    """Custom QuerySet for ProgramPause with annotation methods."""
    def with_annotations(self):
        """Annotate queryset with pause-related fields."""
        return program_pause_annotations(self)

    def active(self):
        """Filter queryset to only active pauses."""
        return self.with_annotations().filter(is_active_gate=True)


class ProgramPause(models.Model):
    """Model representing a pause in the program."""
    pause_start = models.DateTimeField()
    pause_end = models.DateTimeField()
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Attach the custom queryset as the default manager so
    # the ProgramPause.objects is available
    objects = ProgramPauseQuerySet.as_manager()

    # -------------------------------
    # Core pause calculation (dynamic)
    # -------------------------------

    def _calculate_pause_status(self) -> tuple[int, str]:
        """
        Determine pause multiplier and message based on start date and
        duration.

        Rules:
            - Only orders placed 14–11 days before pause start are affected
            - Short pause (<14 days) → multiplier 2
            - Extended pause (>=14 days) → multiplier 3
            - Orders outside this window → multiplier 1
        """
        if not self.pause_start or not self.pause_end:
            return 1, f"{self.reason or 'Unnamed'} not affecting this order"

        today = now()
        days_until_start = (self.pause_start - today).days
        duration = (self.pause_end - self.pause_start).days + 1

        if 11 <= days_until_start <= 14:
            if duration >= 14:
                return (
                    3,
                    (
                        f"{self.reason or 'Unnamed'} Extended pause affecting this order"
                        f"(duration {duration} days)"
                    )
                )
            elif duration >= 1:
                return (
                    2,
                    (
                        f"{self.reason or 'Unnamed'} Short pause affecting this order"
                        f"(duration {duration} days)"
                    )
                )

        return 1, f"{self.reason or 'Unnamed'} not affecting this order"

    @property
    def multiplier(self) -> int:
        """
        Retrieve the pause multiplier based on
        current date and pause settings.
        """
        multiplier, _ = self._calculate_pause_status()
        return multiplier

    @property
    def is_active_gate(self) -> bool:
        """Pause is active if the multiplier is greater than 1."""
        return self.multiplier > 1
   
    def clean(self):
        """Prevent overlapping pauses and invalid dates."""
        super().clean()  # call first for base validation

        now_dt = timezone.now()  # current datetime

        if self.pause_start and self.pause_end:
            if self.pause_end < self.pause_start:
                raise ValidationError(
                    "End datetime cannot be earlier than start datetime."
                )

            # Minimum 11 days out (using datetime)
            min_start_dt = now_dt + timedelta(days=11)
            if self.pause_start < min_start_dt:
                raise ValidationError(
                    "Pause start must be at least 11 days from now."
                )

            # Maximum 14-day pause
            if (self.pause_end - self.pause_start) > timedelta(days=14):
                raise ValidationError(
                    "Program pause cannot be longer than 14 days."
                )

            # Prevent overlapping pauses
            overlap_exists = ProgramPause.objects.exclude(pk=self.pk).filter(
                pause_start__lt=self.pause_end,
                pause_end__gt=self.pause_start,
            ).exists()
            if overlap_exists:
                raise ValidationError(
                    "Another program pause already exists in this period."
                )


class LifeSkillsCoach (models.Model):
    """Model representing a Life Skills coach."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='coaches/', blank=True, null=True)
 
    def __str__(self) -> str:
        return str(self.name)


# Class to represent a Life Skills program
class Program(models.Model):
    """Model representing a Life Skills program."""
    name = models.CharField(max_length=100)
    meeting_time = models.TimeField()
    MeetingDay = models.CharField(
        blank=False,
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
        ],
        max_length=20
    )
    meeting_address = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.name)