from django.apps import AppConfig
class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        # Register model signals.
        from . import signals  # noqa: F401
