"""Compatibility alias for users account HTML views."""

import sys

from .views import account_html as _account_html

sys.modules[__name__] = _account_html
