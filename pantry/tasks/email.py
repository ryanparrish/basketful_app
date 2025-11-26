#food_orders/tasks/email.py
"""Asynchronous tasks for sending emails."""
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings
from celery import shared_task
from log.models import EmailLog


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

@shared_task
def send_email(user, subject, html_template, text_template, email_type, reply_to=None):
    """
    Sends an email if it hasn't already been sent and logs it in EmailLog.
    """
    if EmailLog.objects.filter(user=user, email_type=email_type).exists():
        return  # prevent duplicates

    context = build_email_context(user)
    html_content = render_to_string(html_template, context)
    text_content = render_to_string(text_template, context)
    from_email = None
    to_email = user.email

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        [to_email],
        reply_to=[reply_to] if reply_to else None
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

    EmailLog.objects.create(user=user, email_type=email_type)

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
        reply_to="elizabethp@lovewm.org"
    )