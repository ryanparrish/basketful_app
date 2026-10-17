# middleware.py
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # API clients (SPA) get JSON, never a login-page redirect — the
        # forced-change flow is a web-UI concern (M11).
        if request.path.startswith('/api/'):
            return self.get_response(request)
        if request.user.is_authenticated:
            # M11: the flag lives on UserProfile, not User.
            try:
                must_change = request.user.userprofile.must_change_password
            except Exception:
                must_change = False
            if must_change:
                password_change_url = reverse('password_change')
                if request.path != password_change_url:
                    return redirect(password_change_url)
        return self.get_response(request)
