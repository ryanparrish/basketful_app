# lifeskills/models.py
"""Models for lifeskills app."""
# Standard library imports
from datetime import timedelta
# Django imports
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
# Local imports
from .queryset import program_pause_annotations


class ProgramPauseQuerySet(models.QuerySet):
    """Custom QuerySet for ProgramPause with annotation methods."""
    def with_annotations(self):
        """Annotate queryset with pause-related fields."""
        return program_pause_annotations(self)

    def active(self):
        """Filter queryset to only active pauses."""
        return self.with_annotations().filter(is_active_gate=True)
    
    def all_pauses(self):
        """Return all pauses including archived ones."""
        return self.all()


class ProgramPauseManager(models.Manager):
    """Custom manager that excludes archived pauses by default."""
    def get_queryset(self):
        """Return queryset excluding archived pauses."""
        return super().get_queryset().filter(archived=False)
    
    def all_pauses(self):
        """Return all pauses including archived ones."""
        return super().get_queryset()


class ProgramPause(models.Model):
    """
    Model representing a pause in the program.
    
    Timezone Behavior:
        All date calculations use EST (America/New_York) timezone to ensure
        consistent ordering window detection regardless of server time.
        
        ⚠️ TIMEZONE WARNING: This implementation assumes all participants are in EST.
        If expanding to serve multiple timezones (e.g., PST tenants), you must:
        1. Add a 'timezone' field to Program or ProgramPause model
        2. Update get_est_date() to accept timezone parameter
        3. Pass participant/program timezone to all calculation methods
        
    See Also:
        - apps.lifeskills.utils.get_est_date(): Centralized timezone conversion
        - docs/PROGRAM_PAUSES.md: Full system documentation
    """
    pause_start = models.DateTimeField()
    pause_end = models.DateTimeField()
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    last_resync_at = models.DateTimeField(null=True, blank=True)
    last_resync_by_username = models.CharField(max_length=150, null=True, blank=True)

    class Meta:
        db_table = 'food_orders_programpause'
        app_label = 'lifeskills'

    # Attach the custom manager that excludes archived by default
    objects = ProgramPauseManager.from_queryset(ProgramPauseQuerySet)()

    # -------------------------------
    # Core pause calculation (dynamic)
    # -------------------------------

    @classmethod
    def calculate_multiplier_for_duration(cls, pause_start, pause_end) -> int:
        """
        Calculate the multiplier based on pause duration.
        
        Rules:
            - Short pause (<14 days) → multiplier 2
            - Extended pause (>=14 days) → multiplier 3
        
        Args:
            pause_start: DateTimeField - when pause begins
            pause_end: DateTimeField - when pause ends
            
        Returns:
            int: 2 or 3 based on duration
        """
        if not pause_start or not pause_end:
            return 1
        
        duration = (pause_end - pause_start).days + 1
        
        if duration >= 14:
            return 3
        elif duration >= 1:
            return 2
        
        return 1

    def _calculate_pause_status(self) -> tuple[int, str]:
        """
        Determine pause multiplier and message based on start date and
        duration.

        Rules:
            - Only orders placed 14–10 days before pause start are affected
            - Short pause (<14 days) → multiplier 2
            - Extended pause (>=14 days) → multiplier 3
            - Orders outside this window → multiplier 1
            
        Timezone Behavior:
            Uses EST (America/New_York) for date calculations to ensure consistent
            ordering window detection regardless of server UTC time.
            ⚠️ EST-specific: See class docstring for multi-timezone expansion notes.
        """
        if not self.pause_start or not self.pause_end:
            return 1, f"{self.reason or 'Unnamed'} not affecting this order"

        # Convert both dates to EST for consistent day calculation
        # ⚠️ EST-specific: See get_est_date() docstring for multi-timezone expansion notes
        from .utils import get_est_date
        today_est = get_est_date()
        pause_start_est = get_est_date(self.pause_start)
        days_until_start = (pause_start_est - today_est).days
        duration = (self.pause_end - self.pause_start).days + 1

        if 10 <= days_until_start <= 14:
            multiplier = self.calculate_multiplier_for_duration(
                self.pause_start, self.pause_end
            )
            if multiplier == 3:
                return (
                    3,
                    (
                        f"{self.reason or 'Unnamed'} Extended pause affecting this order"
                        f"(duration {duration} days)"
                    )
                )
            elif multiplier == 2:
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
    
    def archive(self):
        """
        Archive this pause and clean up associated voucher flags.
        
        Sets archived=True, archived_at=now, and resets all vouchers to 
        program_pause_flag=False and multiplier=1.
        """
        from apps.lifeskills.utils import set_voucher_pause_state
        from apps.voucher.models import Voucher
        
        # Reset all vouchers that were flagged for this pause
        active_voucher_ids = list(
            Voucher.objects.filter(active=True, program_pause_flag=True)
            .values_list('id', flat=True)
        )
        if active_voucher_ids:
            set_voucher_pause_state(active_voucher_ids, activate=False, multiplier=1)
        
        # Mark as archived
        self.archived = True
        self.archived_at = timezone.now()
        self.save()
    
    def unarchive(self):
        """
        Unarchive this pause.
        
        Clears archived=False and archived_at=None. If the pause is still 
        within the ordering window, the save signal will re-flag vouchers.
        """
        self.archived = False
        self.archived_at = None
        self.save()
   
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
            min_start_dt = now_dt + timedelta(days=10)
            if self.pause_start < min_start_dt:
                raise ValidationError(
                    "Pause start must be at least 10 days from now."
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


class LifeskillsCoach(models.Model):
    """Model representing a Life Skills coach."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='coaches/', blank=True, null=True)

    class Meta:
        db_table = 'food_orders_lifeskillscoach'
        app_label = 'lifeskills'
 
    def __str__(self) -> str:
        return str(self.name)


# Class to represent a Life Skills program
class Program(models.Model):
    """Model representing a Life Skills program."""
    
    # Split strategy choices for combined orders
    SPLIT_STRATEGY_CHOICES = [
        ('none', 'None (Single Packer)'),
        ('fifty_fifty', '50/50 Split'),
        ('round_robin', 'Round Robin'),
        ('by_category', 'By Category'),
    ]
    
    name = models.CharField(max_length=100)
    meeting_time = models.TimeField(
        default="09:00:00"
    )  # Default meeting time added
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
    meeting_address = models.CharField(max_length=255, blank=True, default='')
    default_split_strategy = models.CharField(
        max_length=20,
        choices=SPLIT_STRATEGY_CHOICES,
        default='none',
        help_text="Default strategy for splitting combined orders among packers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'food_orders_program'
        app_label = 'lifeskills'

    def __str__(self) -> str:
        return str(self.name)
