"""Compatibility alias for users auth HTML views."""

import sys

from .views import auth_html as _auth_html

sys.modules[__name__] = _auth_html
