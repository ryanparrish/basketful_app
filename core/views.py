from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.http import HttpResponse


def index(request):
    return render(request, "core/index.html")


def admin_logout_view(request):
    """Custom logout view for admin users."""
    logout(request)
    return redirect('/admin/login/')
