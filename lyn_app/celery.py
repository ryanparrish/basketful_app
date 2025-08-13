import os
from celery import Celery

# Tell Celery where your settings module is
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lyn_app.settings')

app = Celery('lyn_app')

# Load config from Django settings.py (use CELERY_ prefix)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in installed apps
app.autodiscover_tasks()
