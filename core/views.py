from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.db import connection


def index(request):
    return render(request, "core/index.html")


def admin_logout_view(request):
    """Custom logout view for admin users."""
    logout(request)
    return redirect('/admin/login/')


def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.
    Returns 200 OK if the application is healthy.
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
        }, status=503)

