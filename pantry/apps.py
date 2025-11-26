# apps.py

from django.apps import AppConfig



class PantryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pantry'

    def ready(self):
        import pantry.signals
