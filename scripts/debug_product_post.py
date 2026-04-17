import os
import django

os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings"
django.setup()

from django.test.utils import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()
admin = User.objects.filter(is_staff=True).first()
print("Admin:", admin)

with override_settings(ALLOWED_HOSTS=["*"]):
    client = APIClient()
    client.force_authenticate(user=admin)

    # 1. Minimal JSON
    r = client.post("/api/v1/products/", {"name": "Test", "active": True}, format="json")
    print("Minimal JSON:", r.status_code, r.content.decode())

    # 2. Full form payload
    r2 = client.post("/api/v1/products/", {
        "name": "Test Product",
        "active": True,
        "is_meat": False,
        "quantity_in_stock": 0,
    }, format="json")
    print("Full JSON:", r2.status_code, r2.content.decode())

    # 3. Multipart (FormData without file)
    r3 = client.post("/api/v1/products/", {
        "name": "Test Product",
        "active": True,
        "is_meat": False,
        "quantity_in_stock": 0,
    }, format="multipart")
    print("Multipart no file:", r3.status_code, r3.content.decode())
