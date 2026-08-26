from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        # Register model signals and order-owned Celery task modules.
        from . import feedback_tasks  # noqa: F401
        from . import signals  # noqa: F401
