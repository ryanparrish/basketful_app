import logging

from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.db import connection

_health_logger = logging.getLogger(__name__)


def index(request):
    return render(request, "core/index.html")


def admin_logout_view(request):
    """Custom logout view for admin users."""
    logout(request)
    return redirect('/admin/login/')


def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 OK if the application can reach the database.

    Deliberately returns no internal detail on failure — the status code
    is enough for the load balancer; error detail lives in server logs.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({'status': 'healthy', 'database': 'connected'})
    except Exception:
        _health_logger.exception("Health check DB query failed")
        return JsonResponse({'status': 'unhealthy'}, status=503)

