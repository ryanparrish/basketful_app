"""
URL configuration for lyn_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView
# First-party
from apps.orders import views as order_views
from apps.lifeskills import views as lifeskills_views
from apps.account import views as account_views
from apps.pantry import views as pantry_views
from .views import index

admin.site.site_header = "BasketFul App"
admin.site.site_title = "Love Your Neighbor - Basketful"
admin.site.index_title = "Welcome to Your Admin"

urlpatterns = [
    path('', index, name='index'),
    path('admin/', admin.site.urls),
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
        'accounts/password_change/',
        account_views.CustomPasswordChangeView.as_view(),
        name='password_change',
    ),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(),
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
        'admin/logout/',
        LogoutView.as_view(next_page='/admin/login/'),
        name='admin_logout',
    ),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(
            template_name='registration/logged_out.html'
        ),
        name='logout',
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
