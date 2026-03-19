"""Compatibility alias for admin commerce API views."""

import sys

from .api import admin as _admin

sys.modules[__name__] = _admin
