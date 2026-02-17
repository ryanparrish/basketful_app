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


class ProgramPauseManager(models.Manager):
    """Manager that excludes archived pauses by default."""
    def get_queryset(self):
        """Return queryset excluding archived pauses."""
        return ProgramPauseQuerySet(self.model, using=self._db).filter(archived=False)
    
    def all_pauses(self):
        """Return queryset including archived pauses."""
        return ProgramPauseQuerySet(self.model, using=self._db)


class ProgramPause(models.Model):
    """Model representing a pause in the program."""
    pause_start = models.DateTimeField()
    pause_end = models.DateTimeField()
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Archive fields
    archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'food_orders_programpause'
        app_label = 'lifeskills'

    # Manager that excludes archived by default
    objects = ProgramPauseManager()

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
            - Only orders placed 14–11 days before pause start are affected
            - Short pause (<14 days) → multiplier 2
            - Extended pause (>=14 days) → multiplier 3
            - Orders outside this window → multiplier 1
        """
        if not self.pause_start or not self.pause_end:
            return 1, f"{self.reason or 'Unnamed'} not affecting this order"

        today = timezone.now()
        days_until_start = (self.pause_start - today).days
        duration = (self.pause_end - self.pause_start).days + 1

        if 11 <= days_until_start <= 14:
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
            overlap_exists = ProgramPause.objects.all_pauses().exclude(pk=self.pk).filter(
                archived=False,
                pause_start__lt=self.pause_end,
                pause_end__gt=self.pause_start,
            ).exists()
            if overlap_exists:
                raise ValidationError(
                    "Another program pause already exists in this period."
                )
    
    def archive(self):
        """Archive this pause and clean up vouchers."""
        from apps.lifeskills.utils import set_voucher_pause_state
        from apps.voucher.models import Voucher
        
        # Get all vouchers still flagged for this pause
        flagged_vouchers = Voucher.objects.filter(
            program_pause_flag=True,
            active=True
        )
        
        if flagged_vouchers.exists():
            voucher_ids = list(flagged_vouchers.values_list('id', flat=True))
            set_voucher_pause_state(voucher_ids, activate=False)
        
        # Mark as archived
        self.archived = True
        self.archived_at = timezone.now()
        self.save(update_fields=['archived', 'archived_at'])
    
    def unarchive(self):
        """Unarchive this pause."""
        self.archived = False
        self.archived_at = None
        self.save(update_fields=['archived', 'archived_at'])
    
    def save(self, *args, **kwargs):
        """Handle reactivation when unarchiving an active pause."""
        # Check if we're unarchiving (archived changed from True to False)
        if self.pk:
            try:
                old = ProgramPause.objects.all_pauses().get(pk=self.pk)
                just_unarchived = old.archived and not self.archived
                
                # Save first
                super().save(*args, **kwargs)
                
                # If unarchived and pause is currently active, reactivate vouchers
                if just_unarchived:
                    now = timezone.now()
                    if self.pause_start <= now <= self.pause_end:
                        from apps.lifeskills.utils import set_voucher_pause_state
                        from apps.voucher.models import Voucher
                        
                        multiplier = self.calculate_multiplier_for_duration(
                            self.pause_start, self.pause_end
                        )
                        
                        vouchers = Voucher.objects.filter(active=True, account__active=True)
                        if vouchers.exists():
                            voucher_ids = list(vouchers.values_list('id', flat=True))
                            set_voucher_pause_state(voucher_ids, activate=True, multiplier=multiplier)
                return
            except ProgramPause.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


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
