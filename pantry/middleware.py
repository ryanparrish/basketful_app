# middleware.py
from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if getattr(request.user, 'must_change_password', False):
                password_change_url = reverse('password_change')
                if request.path != password_change_url:
                    return redirect(password_change_url)
        return self.get_response(request)
