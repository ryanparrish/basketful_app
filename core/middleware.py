# core/middleware.py
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import redirect

class ValidationErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except ValidationError as e:
            if request.path.startswith("/admin/") or request.path.startswith("/api/"):
                raise
            messages.error(request, str(e))
            return redirect("participant_dashboard")
