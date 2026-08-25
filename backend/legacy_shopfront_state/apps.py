from django.apps import AppConfig


class LegacyShopfrontStateConfig(AppConfig):
    """Migration/model shell preserving the historical ``shopfront`` app label."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "legacy_shopfront_state"
    label = "shopfront"
    verbose_name = "Legacy storefront state"
