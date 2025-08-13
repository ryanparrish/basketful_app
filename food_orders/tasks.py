from celery import shared_task
from django.contrib.auth.forms import PasswordResetForm

@shared_task
def send_password_reset_email(user_email, domain, use_https):
    """
    Sends a password reset email asynchronously.
    """
    reset_form = PasswordResetForm({'email': user_email})
    if reset_form.is_valid():
        reset_form.save(
            request=None,  # request is optional for email; remove if needed
            use_https=use_https,
            from_email=None,  # defaults to DEFAULT_FROM_EMAIL
            email_template_name='registration/new_user_onboarding.html',
            domain_override=domain
        )
