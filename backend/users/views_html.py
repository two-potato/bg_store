"""Compatibility alias for shared users view helpers."""

import sys

from .views import helpers as _helpers

sys.modules[__name__] = _helpers
