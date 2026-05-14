# apps/account/tasks/email.py
"""Asynchronous tasks for sending emails."""
# Standard library imports
import logging
from datetime import timedelta

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from django.conf import settings
from celery import shared_task


logger = logging.getLogger(__name__)

User = get_user_model()


# ---------------------------
# Email Helpers
# ---------------------------

def build_email_context(user):
    """Generate UID and token for emails."""
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    if getattr(settings, "USE_HTTPS", None) is not None:
        protocol = "https" if settings.USE_HTTPS else "http"
    else:
        protocol = "http" if getattr(settings, "DEBUG", True) else "https"

    domain = settings.DOMAIN_NAME

    return {
        "user": user,
        "domain": domain,
        "uid": uid,
        "token": token,
        "protocol": protocol,
        "site_name": "Basketful",
    }


def get_email_settings():
    """Get the EmailSettings singleton."""
    from core.models import EmailSettings
    return EmailSettings.get_settings()


def get_email_type(email_type_name):
    """Get an EmailType by name."""
    from apps.log.models import EmailType
    return EmailType.objects.filter(name=email_type_name, is_active=True).first()


def create_email_log(user, email_type, subject, status="sent", error_message="", message_id=None):
    """Create a log entry for a sent email."""
    from apps.log.models import EmailLog
    logger.info(
        "[EmailLog] Creating user_id=%s, email_type=%s, status=%s",
        user.id, email_type.name, status
    )
    return EmailLog.objects.create(
        user=user,
        email_type=email_type,
        subject=subject,
        status=status,
        error_message=error_message,
        message_id=message_id or "",
    )


def has_email_been_sent(user, email_type):
    """Check if the email has already been sent to this user."""
    from apps.log.models import EmailLog
    return EmailLog.objects.filter(
        user=user,
        email_type=email_type,
        status="sent"
    ).exists()


def send_email_message(subject, html_content, text_content, to_email,
                       from_email=None, reply_to=None):
    """Send the actual email to the recipient.

    Returns the Mailgun message_id string, or None if unavailable.
    """
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [to_email],
        reply_to=[reply_to] if reply_to else None
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    message_id = getattr(getattr(msg, "anymail_status", None), "message_id", None)
    logger.info("[Email] Sent to=%s subject=%s message_id=%s", to_email, subject, message_id)
    return message_id


# ---------------------------
# Main Email Sending Function
# ---------------------------

@shared_task
def send_email_by_type(user_id, email_type_name, force=False, extra_context=None):
    """
    Send an email based on the EmailType configuration.
    
    Args:
        user_id: The ID of the user to send the email to
        email_type_name: The slug name of the EmailType (e.g., 'onboarding')
        force: If True, skip the duplicate check and send anyway
        extra_context: Additional context variables to pass to the template
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("[Email] User not found: %s", user_id)
        return False
    
    # Get the email type configuration
    email_type = get_email_type(email_type_name)
    if not email_type:
        logger.error("[Email] EmailType not found or inactive: %s", email_type_name)
        return False
    
    # Check for duplicates unless force=True
    if not force and has_email_been_sent(user, email_type):
        logger.info(
            "[Email] Skipped - already sent user_id=%s, email_type=%s",
            user.id, email_type_name
        )
        return False
    
    # Build context
    context = build_email_context(user)
    if extra_context:
        context.update(extra_context)
    
    # Get email settings
    email_settings = get_email_settings()
    
    # Determine from_email and reply_to (type-specific or global default)
    from_email = email_type.from_email or email_settings.get_from_email()
    reply_to = email_type.reply_to or email_settings.get_reply_to()
    
    try:
        # Render content
        subject = email_type.render_subject(context)
        html_content = email_type.render_html(context)
        text_content = email_type.render_text(context)
        
        # Send email
        message_id = send_email_message(
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            to_email=user.email,
            from_email=from_email,
            reply_to=reply_to
        )
        
        # Log success — persist Mailgun message_id for delivery tracking
        create_email_log(user, email_type, subject, status="sent", message_id=message_id)
        return True
        
    except Exception as e:
        logger.exception("[Email] Failed to send email: %s", str(e))
        # Log failure
        create_email_log(
            user, email_type, email_type.subject,
            status="failed", error_message=str(e)
        )
        return False


# ---------------------------
# Convenience Wrapper Tasks
# ---------------------------

@shared_task
def send_new_user_onboarding_email(user_id, force=False):
    """Send onboarding email to a new user.

    Injects participant_customer_number and participant_frontend_url into the
    email context so the template can show the correct login credential.

    Includes a 24-hour deduplication guard: if an onboarding email was already
    sent to this user within the last 24 hours, the task exits silently. This
    prevents duplicate sends from retries, grace-period race conditions, or a
    staff member accidentally submitting the same batch twice.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("[Onboarding] User not found: %s", user_id)
        return False

    # 24-hour deduplication guard
    from apps.log.models import EmailLog
    recently_sent = EmailLog.objects.filter(
        user=user,
        email_type__name='onboarding',
        sent_at__gte=timezone.now() - timedelta(hours=24),
        status='sent',
    ).exists()
    if recently_sent and not force:
        logger.info(
            "[Onboarding] Skipping duplicate — already sent to user_id=%s within 24h",
            user_id,
        )
        return False

    # Build extra context: participant customer number + frontend URL
    extra_context: dict = {
        'participant_frontend_url': getattr(settings, 'PARTICIPANT_FRONTEND_URL', 'https://app.basketful.org'),
    }
    try:
        participant = user.participant
        extra_context['participant_customer_number'] = participant.customer_number or ''
    except Exception:
        extra_context['participant_customer_number'] = ''

    return send_email_by_type(user_id, 'onboarding', force=force, extra_context=extra_context)


@shared_task
def send_password_reset_email(user_id, force=False):
    """Send password reset email to a user."""
    return send_email_by_type(user_id, "password_reset", force=force)


@shared_task
def send_order_window_opened_notification(user_id, program_name, closes_at_str, force=False):
    """Send an order-window-opened notification to a single participant.

    Args:
        user_id:       Django User PK.
        program_name:  Human-readable name of the program whose window opened.
        closes_at_str: ISO-8601 formatted string of when the window closes (UTC).
                       Shown in the email so the participant knows the deadline.
        force:         If True, bypass the per-cycle deduplication guard.
    """
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error("[OrderWindow] User not found: %s", user_id)
        return False

    extra_context = {
        'program_name': program_name,
        'closes_at': closes_at_str,
        'participant_frontend_url': getattr(
            settings, 'PARTICIPANT_FRONTEND_URL', 'https://app.basketful.org'
        ),
    }
    try:
        participant = user.participant
        extra_context['participant_name'] = participant.name or user.get_username()
        extra_context['participant_customer_number'] = participant.customer_number or ''
    except Exception:
        extra_context['participant_name'] = user.get_username()
        extra_context['participant_customer_number'] = ''

    # Dedup for recurring order-window emails is owned by the task layer
    # (EmailLog.sent_at__gte=opens_at in order_window.py).  Bypass the
    # lifetime has_email_been_sent gate — it is only correct for one-shot
    # emails (onboarding, password reset).
    return send_email_by_type(
        user_id, 'order_window_opened', force=True, extra_context=extra_context
    )
