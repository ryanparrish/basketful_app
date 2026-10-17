from django.shortcuts import render, redirect
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.auth import login
from .forms import CustomLoginForm


class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change that resets the must_change_password flag."""
    # M11: was reverse_lazy("home") — no URL named 'home' exists, so a
    # successful change crashed with NoReverseMatch.
    success_url = reverse_lazy("participant_dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        # M11: the flag lives on UserProfile — setting it on User persisted
        # nothing (User has no such field).
        from .models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.must_change_password = False
        profile.save(update_fields=['must_change_password'])
        return response


def _client_ip(request):
    """The client's IP as seen by our proxy.

    Basketful runs behind exactly one proxy (nginx in docker-compose,
    Render's load balancer on Render), and both append the address they saw
    to the END of X-Forwarded-For. Entries to its left come from the client
    and can be forged, and REMOTE_ADDR is the proxy itself, shared by
    everyone. Falls back to REMOTE_ADDR when there is no proxy (local dev).
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
    if hops:
        return hops[-1]
    return request.META.get("REMOTE_ADDR", "unknown")


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
