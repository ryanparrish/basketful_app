from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import CombinedOrder, Order, Program
from celery import shared_task
from datetime import timedelta
from random import choice

@shared_task
def create_weekly_combined_orders():
    today = timezone.localdate()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    for program in Program.objects.all():
        # Skip if a CombinedOrder for this program already exists this week
        if CombinedOrder.objects.filter(
            program=program,
            created_at__date__gte=start_of_week,
            created_at__date__lte=end_of_week
        ).exists():
            continue

        # Get orders for this program created this week
        weekly_orders = Order.objects.filter(
            account__participant__program=program,
            created_at__date__gte=start_of_week,
            created_at__date__lte=end_of_week
        )

        if not weekly_orders.exists():
            continue

        # Pick a packer if available
        packers_for_program = program.packers.all()
        selected_packer = choice(packers_for_program) if packers_for_program.exists() else None

        # Create the combined order
        combined_order = CombinedOrder.objects.create(
            program=program,
            packed_by=selected_packer
        )

        combined_order.orders.set(weekly_orders)
        combined_order.summarized_data = combined_order.summarized_items_by_category()
        combined_order.save(update_fields=['summarized_data'])

User = get_user_model()

@shared_task
def send_new_user_onboarding_email(user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return  # optionally log

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    # Auto-detect protocol based on environment
    if getattr(settings, "USE_HTTPS", None) is not None:
        protocol = "https" if settings.USE_HTTPS else "http"
    else:
        protocol = "http" if getattr(settings, "DEBUG", True) else "https"

    domain = settings.DOMAIN_NAME

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

    html_content = render_to_string("registration/new_user_onboarding.html", context)
    text_content = render_to_string("registration/new_user_onboarding.txt", context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
