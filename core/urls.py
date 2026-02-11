"""
URL configuration for Basketful API.

Django admin has been removed in favor of React-Admin frontend.
API endpoints are served at /api/v1/
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

# First-party
from apps.orders import views as order_views
from apps.lifeskills import views as lifeskills_views
from apps.account import views as account_views
from apps.pantry import views as pantry_views
from .views import index, health_check

urlpatterns = [
    # Django admin (required for admin namespace in tests)
    path('admin/', admin.site.urls),
    
    # Health check endpoint (for load balancers)
    path('api/health/', health_check, name='health_check'),
    
    # API v1 endpoints
    path('api/v1/', include('apps.api.urls', namespace='api')),

    # TinyMCE URLs (for email templates)
    path('tinymce/', include('tinymce.urls')),

    # Legacy participant-facing views
    path('', index, name='index'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html'
        ),
        name='login',
    ),
    path(
        'create-order/',
        pantry_views.product_view,
        name='create_order',
    ),
    path(
        'update-cart/',
        pantry_views.update_cart,
        name='update_cart',
    ),
    path(
        'review-order/',
        order_views.review_order,
        name='review_order',
    ),
    path(
        'submit-order/',
        order_views.submit_order,
        name='submit_order',
    ),
    path(
        'order-success/',
        order_views.order_success,
        name='order_success',
    ),
    path(
        'account/update/',
        pantry_views.account_update_view,
        name='account_update',
    ),
    path(
        'print-customer-list/',
        account_views.print_customer_list,
        name='print_customer_list',
    ),
    path(
        'accounts/password_change/',
        account_views.CustomPasswordChangeView.as_view(),
        name='password_change',
    ),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(
            template_name='registration/logged_out.html'
        ),
        name='logout',
    ),
    path(
        'dashboard/',
        lifeskills_views.participant_dashboard,
        name='participant_dashboard',
    ),
    path(
        "order/<str:order_hash>/",
        order_views.order_detail,
        name="order_detail",
    ),
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html'
        ),
        name='password_reset',
    ),
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )