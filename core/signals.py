"""Signals for core models to handle rule versioning and cache invalidation."""
import hashlib
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache


@receiver(post_save, sender='core.ProgramSettings')
@receiver(post_save, sender='core.OrderWindowSettings')
@receiver(post_save, sender='pantry.ProductLimit')
@receiver(post_save, sender='account.GoFreshSettings')
def update_rules_version(sender, instance, **kwargs):
    """
    Generate MD5 hash of business rules and update Redis cache.
    Called whenever any rule-related model is saved.
    Evicts existing cache key to force immediate update.
    """
    from core.models import ProgramSettings, OrderWindowSettings
    from apps.pantry.models import ProductLimit
    from apps.account.models import GoFreshSettings
    
    # Collect all rule data for hashing
    rule_data = []
    
    # ProgramSettings
    try:
        program_settings = ProgramSettings.objects.first()
        if program_settings:
            rule_data.append(f"program:{program_settings.grace_amount}:{program_settings.grace_enabled}")
    except Exception:
        pass
    
    # OrderWindowSettings
    try:
        order_window = OrderWindowSettings.objects.first()
        if order_window:
            rule_data.append(f"window:{order_window.hours_before_class}:{order_window.hours_before_close}:{order_window.enabled}")
    except Exception:
        pass
    
    # ProductLimits
    try:
        limits = ProductLimit.objects.values_list('id', 'limit', 'limit_scope', 'category_id', 'subcategory_id')
        for limit_data in limits:
            rule_data.append(f"limit:{':'.join(map(str, limit_data))}")
    except Exception:
        pass
    
    # GoFreshSettings
    try:
        go_fresh = GoFreshSettings.objects.first()
        if go_fresh:
            rule_data.append(f"gofresh:{go_fresh.enabled}:{go_fresh.amount_1_2}:{go_fresh.amount_3_5}:{go_fresh.amount_6_plus}")
    except Exception:
        pass
    
    # Generate MD5 hash
    combined_data = '|'.join(rule_data)
    rules_hash = hashlib.md5(combined_data.encode('utf-8')).hexdigest()
    
    # Evict old cache key and set new one with 24-hour TTL
    cache.delete('rules_version')
    cache.set('rules_version', rules_hash, timeout=86400)  # 24 hours
    
    # Update ProgramSettings model with hash (if it's the sender, avoid recursion)
    if sender.__name__ != 'ProgramSettings':
        try:
            program_settings = ProgramSettings.objects.first()
            if program_settings and program_settings.rules_version != rules_hash:
                ProgramSettings.objects.filter(pk=program_settings.pk).update(rules_version=rules_hash)
        except Exception:
            pass


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
            # Fail silently to avoid breaking order flow
            pass
