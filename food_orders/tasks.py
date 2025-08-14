from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def send_new_user_onboarding_email(user_id, domain, use_https=True):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return  # optionally log

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    protocol = "https" if use_https else "http"

    context = {
        "user": user,
        "domain": domain,
        "uid": uid,
        "token": token,
        "protocol": protocol,
    }

    subject = "Welcome! Set Your Password"
    from_email = None  # defaults to DEFAULT_FROM_EMAIL
    to_email = user.email

    # Render templates
    html_content = render_to_string("registration/new_user_onboarding.html", context)
    text_content = render_to_string("registration/new_user_onboarding.txt", context)

    # Create and send email
    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
