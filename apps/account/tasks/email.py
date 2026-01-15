# apps/account/tasks/email.py
"""Asynchronous tasks for sending emails."""
# Standard library imports
import logging

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
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


def create_email_log(user, email_type, subject, status="sent", error_message=""):
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
        error_message=error_message
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
    """Send the actual email to the recipient."""
    msg = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [to_email],
        reply_to=[reply_to] if reply_to else None
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()
    logger.info("[Email] Sent to=%s subject=%s", to_email, subject)


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
        send_email_message(
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            to_email=user.email,
            from_email=from_email,
            reply_to=reply_to
        )
        
        # Log success
        create_email_log(user, email_type, subject, status="sent")
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
    """Send onboarding email to a new user."""
    return send_email_by_type(user_id, "onboarding", force=force)


@shared_task
def send_password_reset_email(user_id, force=False):
    """Send password reset email to a user."""
    return send_email_by_type(user_id, "password_reset", force=force)
