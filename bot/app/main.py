"""
Backward-compatible entrypoint.

Default bot runtime is shop bot.
Use app.main_notify:app for notifications bot.
"""

from .main_shop import app  # noqa: F401

