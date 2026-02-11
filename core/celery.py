import os
import json
import sys
from decimal import Decimal
from celery import Celery
from kombu.serialization import register
from kombu.utils.json import JSONEncoder
import ulid

# --- Django settings module ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# --- Define Celery app ---
app = Celery("core")

# --- Override for test mode BEFORE loading Django settings ---
# Detect pytest via environment variable or sys.modules
is_test = (os.environ.get('PYTEST_CURRENT_TEST') or 
          'pytest' in sys.modules or 
          any('pytest' in arg for arg in sys.argv))

if is_test:
    # Set eager mode before loading Django config
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True

# Load Django settings (this may override if CELERY_* env vars are set)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Re-apply test mode after Django config to ensure it takes precedence
if is_test:
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


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
# Moved from lyn_app/celery.py
# Celery configuration
