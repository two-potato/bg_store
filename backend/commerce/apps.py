from django.apps import AppConfig


class CommerceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "commerce"

    def ready(self) -> None:
        # Import signals
        from . import signals  # noqa: F401
        return super().ready()

