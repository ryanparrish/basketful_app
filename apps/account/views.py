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
