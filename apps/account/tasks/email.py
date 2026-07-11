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
from django.utils import timezone, translation
from django.conf import settings
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError


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

    # Staff-editable override (EmailSettings singleton) wins over the
    # DOMAIN_NAME environment setting — fixes dead password-reset links
    # when the env var is unset in production (Issue #83).
    domain = get_email_settings().get_backend_domain()

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


def create_email_log(user, email_type, subject, status="sent", error_message="",
                     message_id=None, is_test=False):
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
        is_test=is_test,
    )


def has_email_been_sent(user, email_type):
    """Check if the email has already been sent to this user.

    Test sends from the email studio don't count — a staff member
    previewing the onboarding email must not block the real one.
    """
    from apps.log.models import EmailLog
    return EmailLog.objects.filter(
        user=user,
        email_type=email_type,
        status="sent",
        is_test=False,
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

@shared_task(bind=True, max_retries=3)
def send_email_by_type(self, user_id, email_type_name, force=False, extra_context=None):
    """
    Send an email based on the EmailType configuration.

    Retries up to 3 times with exponential backoff (60 s, 120 s, 240 s) on
    any transient send failure.  An EmailLog failure entry is only written
    after all retries are exhausted, so the failure log represents a
    permanently undeliverable message rather than a transient blip.

    Args:
        user_id:        The ID of the user to send the email to.
        email_type_name: The slug name of the EmailType (e.g., 'onboarding').
        force:          If True, skip the duplicate check and send anyway.
        extra_context:  Additional context variables to pass to the template.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
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
    
    # Render in the participant's preferred language: the modeltranslation
    # descriptors on EmailType resolve subject_es/html_content_es under
    # override, with automatic English fallback when a translation is blank.
    participant = getattr(user, 'participant', None)
    email_language = getattr(participant, 'preferred_language', None) or 'en'

    try:
        # Render content
        with translation.override(email_language):
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
        logger.warning(
            "[Email] Send failed (attempt %d/3) user_id=%s email_type=%s: %s",
            self.request.retries + 1, user_id, email_type_name, str(e),
        )
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error(
                "[Email] All retries exhausted user_id=%s email_type=%s: %s",
                user_id, email_type_name, str(e),
            )
            try:
                create_email_log(
                    user, email_type, email_type.subject,
                    status="failed", error_message=str(e),
                )
            except Exception:
                logger.exception(
                    "[Email] Failed to write failure log for user_id=%s", user_id
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
        'participant_frontend_url': get_email_settings().get_participant_frontend_url(),
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
        closes_at_str: Human-readable string describing when the window closes,
                       e.g. "Monday, June 3 at 9:00 AM", formatted in the
                       application's configured timezone (settings.TIME_ZONE).
                       Shown directly in the email body.
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
        'participant_frontend_url': get_email_settings().get_participant_frontend_url(),
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


@shared_task
def retry_failed_emails():
    """Re-dispatch email sends that permanently failed within the last 24 hours.

    Acts as a soft dead-letter queue: any EmailLog row with status='failed'
    and retry_count < 3 that was created within the last 24 hours is
    re-dispatched via send_email_by_type with force=True.

    The 24-hour window keeps retries scoped to same-day failures where the
    email is still timely (password resets expire, order-window notices
    become stale).  Failures older than 24 hours are left untouched.

    retry_count is incremented before dispatch so a concurrent scheduler
    tick cannot double-queue the same row.
    """
    from apps.log.models import EmailLog

    cutoff = timezone.now() - timedelta(hours=24)
    candidates = EmailLog.objects.filter(
        status="failed",
        retry_count__lt=3,
        sent_at__gte=cutoff,
        is_test=False,  # a failed studio test send must never be re-sent for real
    ).select_related("email_type")

    dispatched = 0
    for log_entry in candidates:
        try:
            # Increment first — prevents a second scheduler tick from
            # re-queuing the same row before the Celery task has started.
            EmailLog.objects.filter(pk=log_entry.pk).update(
                retry_count=log_entry.retry_count + 1
            )
            send_email_by_type.delay(
                log_entry.user_id,
                log_entry.email_type.name,
                force=True,
            )
            dispatched += 1
            logger.info(
                "[EmailDLQ] Re-dispatched user_id=%s email_type=%s (attempt %d)",
                log_entry.user_id,
                log_entry.email_type.name,
                log_entry.retry_count + 1,
            )
        except Exception:
            logger.exception(
                "[EmailDLQ] Failed to re-dispatch user_id=%s email_type=%s",
                log_entry.user_id,
                log_entry.email_type.name,
            )

    if dispatched:
        logger.info("[EmailDLQ] Retried %d failed email(s)", dispatched)
