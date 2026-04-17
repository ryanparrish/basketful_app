"""Signals for core models to handle rule versioning and cache invalidation."""
import hashlib
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

logger = logging.getLogger(__name__)

RULES_VERSION_CACHE_KEY = 'rules_version'
RULES_VERSION_TTL = 86400  # 24 hours


def _compute_rules_hash() -> str:
    """
    Pure function: reads current rule state from the DB and returns an
    MD5 hex-digest string.  Does NOT write to the cache or any model.

    Call this whenever you need the hash without triggering side-effects
    (e.g. cache-miss recovery in a GET endpoint).
    """
    from core.models import ProgramSettings, OrderWindowSettings
    from apps.pantry.models import ProductLimit
    from apps.account.models import GoFreshSettings

    rule_data = []

    try:
        program_settings = ProgramSettings.objects.first()
        if program_settings:
            rule_data.append(
                f"program:{program_settings.grace_amount}:{program_settings.grace_enabled}"
            )
    except Exception as e:
        logger.warning("rules_hash: failed to read ProgramSettings: %s", e)

    try:
        order_window = OrderWindowSettings.objects.first()
        if order_window:
            rule_data.append(
                f"window:{order_window.hours_before_class}:"
                f"{order_window.hours_before_close}:{order_window.enabled}"
            )
    except Exception as e:
        logger.warning("rules_hash: failed to read OrderWindowSettings: %s", e)

    try:
        limits = ProductLimit.objects.values_list(
            'id', 'limit', 'limit_scope', 'category_id', 'subcategory_id'
        )
        for limit_data in limits:
            rule_data.append(f"limit:{':'.join(map(str, limit_data))}")
    except Exception as e:
        logger.warning("rules_hash: failed to read ProductLimit: %s", e)

    try:
        go_fresh = GoFreshSettings.objects.first()
        if go_fresh:
            rule_data.append(
                f"gofresh:{go_fresh.enabled}:{go_fresh.amount_1_2}:"
                f"{go_fresh.amount_3_5}:{go_fresh.amount_6_plus}"
            )
    except Exception as e:
        logger.warning("rules_hash: failed to read GoFreshSettings: %s", e)

    return hashlib.md5('|'.join(rule_data).encode('utf-8'), usedforsecurity=False).hexdigest()


@receiver(post_save, sender='core.ProgramSettings')
@receiver(post_save, sender='core.OrderWindowSettings')
@receiver(post_save, sender='pantry.ProductLimit')
@receiver(post_save, sender='account.GoFreshSettings')
def update_rules_version(sender, instance, **kwargs):
    """
    Recompute and cache the rules version hash whenever a rule-related
    model is saved.  Also back-fills ProgramSettings.rules_version via
    an UPDATE (avoids a recursive post_save loop).
    """
    rules_hash = _compute_rules_hash()

    cache.delete(RULES_VERSION_CACHE_KEY)
    cache.set(RULES_VERSION_CACHE_KEY, rules_hash, timeout=RULES_VERSION_TTL)

    # Back-fill ProgramSettings.rules_version; skip when ProgramSettings is
    # the sender to avoid a recursive post_save loop.
    if sender.__name__ != 'ProgramSettings':
        try:
            from core.models import ProgramSettings
            ps = ProgramSettings.objects.first()
            if ps and ps.rules_version != rules_hash:
                ProgramSettings.objects.filter(pk=ps.pk).update(rules_version=rules_hash)
        except Exception as e:
            logger.warning("rules_version: failed to back-fill ProgramSettings: %s", e)


@receiver(post_save, sender='log.GraceAllowanceLog')
def notify_admin_grace_usage(sender, instance, created, **kwargs):
    """
    Create admin notification when participant uses grace allowance.
    Only triggers when a new log entry is created and participant proceeded.
    """
    if created and instance.proceeded:
        # Log to Django admin log
        try:
            from django.contrib.contenttypes.models import ContentType
            from django.contrib.auth.models import User
            from django.contrib.admin.models import LogEntry, CHANGE
            
            # Get staff users to notify (optional: could filter by permission)
            staff_users = User.objects.filter(is_staff=True, is_active=True)
            
            for user in staff_users:
                LogEntry.objects.log_action(
                    user_id=user.pk,
                    content_type_id=ContentType.objects.get_for_model(instance).pk,
                    object_id=instance.pk,
                    object_repr=str(instance),
                    action_flag=CHANGE,
                    change_message=f"Grace allowance used: {instance.participant.user.get_full_name() or instance.participant.user.username} - ${instance.amount_over} over budget"
                )
        except Exception as e:
            # Fail silently to avoid breaking order flow, but log so operators know.
            logger.warning("notify_admin_grace_usage: failed to create LogEntry: %s", e)
