"""Compatibility alias for users seller HTML views."""

import sys

from .views import seller_html as _seller_html

sys.modules[__name__] = _seller_html
