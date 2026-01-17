from django.shortcuts import render, redirect
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.auth import login
from .forms import CustomLoginForm


class CustomPasswordChangeView(PasswordChangeView):
    """Custom password change that resets the must_change_password flag."""
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.user.must_change_password = False
        self.request.user.save()
        return response


def custom_login_view(request):
    """Login view with captcha enabled after 3 failed attempts."""
    show_captcha = request.session.get("login_failures", 0) >= 3

    if request.method == "POST":
        form = CustomLoginForm(
            data=request.POST, request=request, use_captcha=show_captcha
        )
        if form.is_valid():
            login(request, form.get_user())
            request.session["login_failures"] = 0
            return redirect("participant_dashboard")
        else:
            request.session["login_failures"] = request.session.get(
                "login_failures", 0
            ) + 1
    else:
        form = CustomLoginForm(use_captcha=show_captcha)

    return render(
        request,
        "registration/login.html",
        {"form": form, "show_captcha": show_captcha},
    )


def print_customer_list(request):
    """Print view for customer list grouped by program."""
    from core.models import BrandingSettings
    from .models import Participant
    
    # Get participant IDs from session
    participant_ids = request.session.get('print_customer_ids', [])
    
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
    }
    
    return render(request, 'account/print_customer_list.html', context)
