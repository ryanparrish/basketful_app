import django
import os
import json
import traceback
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from apps.orders.api.views import OrderViewSet
from apps.orders.models import Order
from unittest.mock import patch

user = User.objects.filter(is_staff=True).first()
order = Order.objects.first()
print(f'order id={order.id} status={order.status}')

factory = RequestFactory()
request = factory.post(
    '/api/v1/orders/bulk_update_status/',
    data=json.dumps({'order_ids': [order.id], 'new_status': 'confirmed'}),
    content_type='application/json',
)
request.user = user

with patch('apps.api.permissions.IsStaffUser.has_permission', return_value=True):
    with patch('rest_framework.permissions.IsAuthenticated.has_permission', return_value=True):
        try:
            view = OrderViewSet.as_view({'post': 'bulk_update_status'})
            response = view(request)
            print('status:', response.status_code)
            print('data:', response.data)
        except Exception:
            traceback.print_exc()
