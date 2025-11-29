# apps/account/tasks/email.py
"""Asynchronous tasks for sending emails."""
# Standard library imports
import logging

# Django imports
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from celery import shared_task
# First-party imports
from apps.log.models import EmailLog


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
    }


def has_email_been_sent(user, email_type) -> bool:
    """Check if the email has already been sent to this user"""
    return EmailLog.objects.filter(user=user, email_type=email_type).exists()


def create_email_log(user, email_type):
    """Create a log entry for a sent email"""
    logger.info("[EmailLog] Creating user_id=%s, email_type=%s", user.id, email_type)
    return EmailLog.objects.create(user=user, email_type=email_type)


def build_email_content(user, html_template, text_template) -> tuple[str, str]:
    """Render HTML and text content for the email"""
    context = build_email_context(user)
    html_content = render_to_string(html_template, context)
    text_content = render_to_string(text_template, context)
    return html_content, text_content


def send_email_message(subject, html_content, text_content, to_email, reply_to=None):
    """Send the actual email to the recipient"""
    from_email = None
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


@shared_task
def send_email(user, subject, html_template, text_template, email_type, reply_to=None):
    """Send an email if it hasn't already been sent and log it"""
    if has_email_been_sent(user, email_type):
        logger.info("[Email] skipped - already sent user_id=%s, email_type=%s", user.id, email_type)
        return

    html_content, text_content = build_email_content(user, html_template, text_template)
    send_email_message(subject, html_content, text_content, user.email, reply_to)
    create_email_log(user, email_type)

# ---------------------------
# Onboarding & Password Reset Tasks
# ---------------------------

@shared_task
def send_new_user_onboarding_email(user_id):
    """Send onboarding email to a new user."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    send_email(
        user=user,
        subject="Welcome to Love Your Neighbor!",
        html_template="registration/new_user_onboarding.html",
        text_template="registration/new_user_onboarding.txt",
        email_type="onboarding",
        reply_to="elizabethp@lovewm.org"
    )


@shared_task
def send_password_reset_email(user_id):
    """Send password reset email to a user."""
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    send_email(
        user=user,
        subject="Set Your Password",
        html_template="registration/password_reset_email.html",
        text_template="registration/password_reset_email.txt",
        email_type="password_reset",
        reply_to="it@loveyourneighbor.org"  # Corrected reply_to value
    )
