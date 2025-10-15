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
from food_orders import views
from food_orders.views import participant_dashboard,CustomPasswordChangeView
from django.contrib.auth.views import LoginView
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path, include
from food_orders.forms import CustomLoginForm
admin.site.site_header = "BasketFull App"  # Changes the main header
admin.site.site_title = "Love Your Neighbor - Basketfull"  # Changes the HTML <title> tag
admin.site.index_title = "Welcome to Your Admin"  # Changes the title on the admin index page

urlpatterns = [
    path('accounts/password_change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('index/', views.index, name='index'),
    path('login/', views.custom_login_view, name='participant_login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(),name='logout'),
    path('dashboard/', participant_dashboard, name='participant_dashboard'),
    path('orders/create/', views.product_view, name='create_order'),
    path('accounts/update/', views.account_update_view, name='account_update'),
    path('order/update_cart/', views.update_cart, name='update_cart'),
    path('order/review/',views.review_order, name='review_order'),
    path('order/submit/', views.submit_order, name='submit_order'),
    path('order/<str:order_hash>/', views.order_detail, name='order_detail'),
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('admin/logout/', LogoutView.as_view(next_page='/admin/login/'), name='admin_logout'),
    path('accounts/logout/', auth_views.LogoutView.as_view(template_name='registration/logged_out.html'),name='logout'),
    path("order/success/", views.order_success, name="order_success"),

    path('password_reset/', 
         auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), 
         name='password_reset'),

    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), 
         name='password_reset_done'),

    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), 
         name='password_reset_confirm'),

    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), 
         name='password_reset_complete'),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)