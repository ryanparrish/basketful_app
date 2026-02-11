from django.apps import AppConfig


class LifeskillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.lifeskills'
    label = 'lifeskills'

    def ready(self):
        """Import signals when app is ready."""
        import apps.lifeskills.signals  # noqa: F401
