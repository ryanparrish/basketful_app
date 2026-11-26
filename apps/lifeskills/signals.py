# lifeskills/signals.py
"""Signals for lifeskills app: coach user sync."""
# Standard library imports
import logging
# Django imports
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
# Local imports
from .models import LifeskillsCoach

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
