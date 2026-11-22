from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.auth import login
from .forms import CustomLoginForm
from .models import UserProfile
from core.client_ip import get_client_ip


class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change that resets the must_change_password flag."""
    # M11: was reverse_lazy("home") — no URL named 'home' exists, so a
    # successful change crashed with NoReverseMatch.
    success_url = reverse_lazy("participant_dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        UserProfile.objects.filter(user=self.request.user).update(
            must_change_password=False
        )
        return response


def password_reset_link(request, uidb64, token):
    """Send an emailed reset link into the app that finishes it (#137).

    The reset and onboarding emails build this URL with
    {% url 'password_reset_confirm' %}, and staff edit those templates, so
    the URL stays; Django's reset page behind it is gone. Participants go
    to the participant app (in their language), everyone else to the staff
    app. A link that doesn't decode still goes to the participant app,
    which explains it has expired.
    """
    from django.contrib.auth import get_user_model
    from django.utils.http import urlsafe_base64_decode

    User = get_user_model()
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    participant = getattr(user, 'participant', None) if user else None
    if user is not None and participant is None:
        return redirect(f"{settings.STAFF_APP_PATH}reset-password/{uidb64}/{token}")

    target = f"{settings.PARTICIPANT_APP_PATH}reset/{uidb64}/{token}"
    language = getattr(participant, 'preferred_language', None)
    if language:
        target += f"?lang={language}"
    return redirect(target)


def participant_app_page(page):
    """A view that sends the browser to a page of the participant app."""
    def view(request, *args, **kwargs):
        return redirect(f"{settings.PARTICIPANT_APP_PATH}{page}")
    return view


def _client_ip(request):
    """The client's IP; see core.client_ip for how it's chosen (#111)."""
    return get_client_ip(request) or "unknown"


def custom_login_view(request):
    """Login view with captcha enabled after 3 failed attempts."""
    from django.core.cache import cache
    from django.utils.http import url_has_allowed_host_and_scheme

    def _failure_keys():
        # Review #107: count failures per username/IP in the cache, not
        # the session — clearing the session cookie reset the session
        # count and the captcha never appeared.
        keys = []
        username = (request.POST.get("username") or "").strip().lower()
        if username:
            keys.append(f"login_failures:user:{username}")
        keys.append(f"login_failures:ip:{_client_ip(request)}")
        return keys

    def _failure_count():
        return max([cache.get(k, 0) for k in _failure_keys()] or [0])

    show_captcha = _failure_count() >= 3
    next_url = request.POST.get("next") or request.GET.get("next")

    if request.method == "POST":
        form = CustomLoginForm(
            data=request.POST, request=request, use_captcha=show_captcha
        )
        if form.is_valid():
            login(request, form.get_user())
            for k in _failure_keys():
                cache.delete(k)
            # Review #107: honor ?next= (e.g. login_required redirects from
            # /admin/...) instead of always landing on participant_dashboard.
            if next_url and url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                return redirect(next_url)
            return redirect("participant_dashboard")
        else:
            for k in _failure_keys():
                cache.set(k, cache.get(k, 0) + 1, 3600)
    else:
        form = CustomLoginForm(use_captcha=show_captcha)

    return render(
        request,
        "registration/login.html",
        {"form": form, "show_captcha": show_captcha, "next": next_url},
    )


def print_customer_list(request):
    """Print view for customer list grouped by program."""
    from core.models import BrandingSettings
    from .models import Participant
    
    # Get participant IDs from session
    participant_ids = request.session.get('print_customer_ids', [])
    
    # Check if user is confirming selection (POST with selected IDs)
    if request.method == 'POST':
        selected_ids = request.POST.getlist('selected_participants')
        participant_ids = [int(pid) for pid in selected_ids]
        auto_print = True
    else:
        auto_print = False
    
    # Get participants and group by program
    participants = Participant.objects.filter(
        id__in=participant_ids
    ).select_related('program').order_by('program__name', 'name')
    
    # Group by program
    programs = {}
    for participant in participants:
        program_name = participant.program.name if participant.program else "No Program"
        if program_name not in programs:
            programs[program_name] = []
        programs[program_name].append(participant)
    
    # Get branding settings
    branding = BrandingSettings.get_settings()
    
    context = {
        'programs': programs,
        'branding': branding,
        'total_customers': len(participants),
        'auto_print': auto_print,
    }
    
    return render(request, 'account/print_customer_list.html', context)
