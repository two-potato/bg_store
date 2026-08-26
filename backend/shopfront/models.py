"""Compatibility model imports for the historical ``shopfront`` app label.

The actual persisted model definitions now live in ``legacy_shopfront_state``.
This shim exists only while runtime imports are migrated away from ``shopfront``.
"""

from legacy_shopfront_state.models import *  # noqa: F403
