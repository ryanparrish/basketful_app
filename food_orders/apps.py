# apps.py

from django.apps import AppConfig

class FoodOrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'food_orders'

    def ready(self):
        import food_orders.signals
