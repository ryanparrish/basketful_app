from django.apps import AppConfig


class PantryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pantry'
    label = 'pantry'

    def ready(self):
        import apps.pantry.signals  # noqa: F401
