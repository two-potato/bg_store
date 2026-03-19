from django.apps import AppConfig
class ShopfrontConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shopfront"

    def ready(self):
        from . import signals  # noqa: F401
