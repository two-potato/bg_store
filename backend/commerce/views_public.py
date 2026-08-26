"""Compatibility alias for public commerce API views."""

import sys

from .api import public as _public

sys.modules[__name__] = _public
