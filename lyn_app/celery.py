import os
import json
import ulid
from decimal import Decimal
from celery import Celery
from kombu.serialization import register
from kombu.utils.json import JSONEncoder

# --- Django settings module ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lyn_app.settings")

# --- Define Celery app ---
app = Celery("lyn_app")
app.config_from_object("django.conf:settings", namespace="CELERY")

# --- Custom JSON encoder for ULID + Decimal ---
class ExtendedJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, ulid.ULID):
            return str(o)
        if isinstance(o, Decimal):
            return float(o)  # or str(o) if you need exact precision
        return super().default(o)

# --- Register the custom serializer ---
register(
    "custom_json",
    lambda obj: json.dumps(obj, cls=ExtendedJSONEncoder),
    json.loads,
    content_type="application/x-custom-json",
    content_encoding="utf-8",
)

# --- Celery config ---
app.conf.task_serializer = "custom_json"
app.conf.result_serializer = "custom_json"
app.conf.accept_content = ["custom_json", "json"]

# --- Auto-discover tasks ---
app.autodiscover_tasks()
