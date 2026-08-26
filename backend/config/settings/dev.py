from .base import *  # noqa: F403,F401

INSTALLED_APPS = [  # noqa: F405
    "legacy_shopfront_state.apps.LegacyShopfrontStateConfig" if app == "shopfront" else app
    for app in INSTALLED_APPS  # noqa: F405
]

DEBUG = True
