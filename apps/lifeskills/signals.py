# lifeskills/signals.py
"""Signals for lifeskills app to handle ProgramPause events and coach user sync."""
# Standard library imports
import logging
# Django imports
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
# First-party imports
from apps.voucher.models import Voucher
from apps.voucher.tasks.voucher_scheduling import schedule_voucher_tasks
from apps.log.signals import VoucherLogger
from apps.lifeskills.tasks.program_pause import (
    update_voucher_flag_task,
    deactivate_expired_pause_vouchers,
)
# Local imports
from .models import ProgramPause, LifeskillsCoach

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Coach → User sync signals
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=LifeskillsCoach)
def track_coach_user_change(sender, instance, **kwargs):
    """Stash the previous user FK so post_save can diff it."""
    if instance.pk:
        try:
            instance._prev_user = LifeskillsCoach.objects.get(pk=instance.pk).user
        except LifeskillsCoach.DoesNotExist:
            instance._prev_user = None
    else:
        instance._prev_user = None


@receiver(post_save, sender=LifeskillsCoach)
def sync_coach_user_group(sender, instance, created, **kwargs):
    """
    Keep the 'Lifeskills Coach' group and is_staff flag in sync with coach.user.

    - When coach.user is assigned → add to group, set is_staff=True
    - When coach.user is removed/changed → remove old user from group,
      revoke is_staff (unless they're a superuser or still in another group
      that implies staff access)
    """
    from django.contrib.auth.models import Group

    try:
        coach_group = Group.objects.get(name='Lifeskills Coach')
    except Group.DoesNotExist:
        logger.warning("'Lifeskills Coach' group not found — run migrations.")
        return

    prev_user = getattr(instance, '_prev_user', None)
    new_user = instance.user

    # Revoke access for old user if user changed
    if prev_user and prev_user != new_user:
        prev_user.groups.remove(coach_group)
        # Only remove is_staff if they're not a superuser or other staff-role group
        STAFF_GROUPS = {'Staff', 'Admin', 'Lifeskills Coach'}
        remaining_staff_groups = prev_user.groups.filter(
            name__in=STAFF_GROUPS
        ).exclude(name='Lifeskills Coach').exists()
        if not prev_user.is_superuser and not remaining_staff_groups:
            prev_user.is_staff = False
            prev_user.save(update_fields=['is_staff'])
        logger.info(
            "Removed user '%s' from Lifeskills Coach group (coach reassigned).",
            prev_user.username,
        )

    # Grant access for new user
    if new_user:
        new_user.groups.add(coach_group)
        if not new_user.is_staff:
            new_user.is_staff = True
            new_user.save(update_fields=['is_staff'])
        logger.info(
            "Added user '%s' to Lifeskills Coach group.",
            new_user.username,
        )




@receiver(post_save, sender=ProgramPause)
def handle_program_pause(sender, instance, created, **kwargs):
    """
    Signal to handle ProgramPause events and delegate voucher updates.
    
    If pause is created within the 11-14 day ordering window, immediately
    flag vouchers with appropriate multiplier and schedule smart deactivation.
    Otherwise, schedule activation for pause_start time.
    
    Timezone Behavior:
        Uses EST (America/New_York) for all date calculations to ensure
        ordering window (11-14 days) is calculated consistently.
        ⚠️ Assumes all participants are in EST timezone.
    """
    logger.debug("=== Signal Triggered for ProgramPause ID=%s ===", instance.id)
    logger.debug(
        "Created=%s, pause_start=%s, pause_end=%s",
        created,
        instance.pause_start,
        instance.pause_end,
    )

    if getattr(instance, "_skip_signal", False):
        logger.debug("Skip signal flag detected; exiting to avoid recursion")
        return

    # Only active vouchers with active accounts
    vouchers = Voucher.objects.filter(active=True, account__active=True)
    if not vouchers.exists():
        logger.debug("No active vouchers found; exiting signal.")
        return

    # Convert to EST for consistent day calculation across all timezones
    # ⚠️ EST-specific implementation - see ProgramPause model docstring for expansion notes
    from apps.lifeskills.utils import get_est_date
    now = timezone.now()  # Keep for task scheduling comparisons
    today_est = get_est_date(now)
    pause_start_est = get_est_date(instance.pause_start)
    days_until_start = (pause_start_est - today_est).days

    # Check if we're in the 11-14 day ordering window
    if 10 <= days_until_start <= 14:
        logger.info(
            "ProgramPause ID=%s is within 10-14 day ordering window "
            "(starts in %d days). Flagging vouchers immediately.",
            instance.id,
            days_until_start
        )
        
        # Calculate appropriate multiplier based on duration
        multiplier = ProgramPause.calculate_multiplier_for_duration(
            instance.pause_start, instance.pause_end
        )
        
        # Immediately activate vouchers with the calculated multiplier
        voucher_ids = list(vouchers.values_list('id', flat=True))
        update_voucher_flag_task.delay(
            voucher_ids, 
            multiplier=multiplier, 
            activate=True,
            program_pause_id=instance.id
        )
        
        logger.info(
            "Flagged %d vouchers with multiplier=%d for ProgramPause ID=%s",
            len(voucher_ids),
            multiplier,
            instance.id
        )
        
        # Schedule smart deactivation task
        # Start checking after the earliest participant's order window closes
        from core.utils import get_next_class_datetime
        from apps.account.models import Participant
        
        earliest_close = None
        for participant in Participant.objects.filter(active=True, program__isnull=False):
            next_class = get_next_class_datetime(participant)
            if next_class:
                # Window closes at class time (or hours_before_close if configured)
                from core.models import OrderWindowSettings
                settings = OrderWindowSettings.get_settings()
                from datetime import timedelta
                window_closes = next_class - timedelta(hours=settings.hours_before_close)
                # Add 5-minute buffer
                close_with_buffer = window_closes + timedelta(minutes=5)
                
                if earliest_close is None or close_with_buffer < earliest_close:
                    earliest_close = close_with_buffer
        
        if earliest_close and earliest_close > now:
            logger.info(
                "Scheduling deactivation task for ProgramPause ID=%s at %s "
                "(earliest window close + 5min buffer)",
                instance.id,
                earliest_close
            )
            deactivate_expired_pause_vouchers.apply_async(
                args=[instance.id],
                eta=earliest_close
            )
        else:
            logger.warning(
                "Could not determine earliest window close time for ProgramPause ID=%s",
                instance.id
            )
    else:
        # Outside ordering window - use original scheduling logic
        logger.info(
            "ProgramPause ID=%s is outside 11-14 day window (starts in %d days). "
            "Scheduling tasks for future execution.",
            instance.id,
            days_until_start
        )
        try:
            schedule_voucher_tasks(
                vouchers,
                activate_time=instance.pause_start,
                deactivate_time=instance.pause_end,
            )
            logger.debug(
                "Tasks scheduled successfully for ProgramPause ID=%s affecting %d vouchers",
                instance.id,
                vouchers.count(),
            )
        except Exception as e:
            for voucher in vouchers:
                VoucherLogger.error(
                    voucher.account.participant,
                    f"Unexpected error in ProgramPause signal: {e}",
                    voucher=voucher,
                )
            raise

    logger.debug("=== End of Signal ===\n")