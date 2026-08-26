from __future__ import annotations

from hashlib import sha1

from django.conf import settings


RECOMMENDATION_VARIANTS = ("control", "ranked_v2", "ml_v1")
SESSION_KEY = "shopfront_recommendation_experiment_v1"


def recommendation_variant_for_request(request, surface: str = "") -> str:
    """Handle recommendation variant for request."""
    state = request.session.get(SESSION_KEY)
    if state in RECOMMENDATION_VARIANTS:
        if state == "ml_v1" and not _ml_allowed_for_surface(surface):
            return "ranked_v2"
        return str(state)
    user = getattr(request, "user", None)
    seed = f"user:{getattr(user, 'id', 0) or 0}" if getattr(user, "is_authenticated", False) else (
        f"session:{request.session.session_key or request.META.get('REMOTE_ADDR', '')}"
    )
    bucket = int(sha1(seed.encode("utf-8")).hexdigest(), 16) % 100
    if _ml_allowed_for_surface(surface) and bucket < int(getattr(settings, "RECOMMENDATION_ML_ROLLOUT_PERCENT", 0) or 0):
        variant = "ml_v1"
    else:
        variant = "ranked_v2" if bucket >= 50 else "control"
    request.session[SESSION_KEY] = variant
    request.session.modified = True
    return variant


def _ml_allowed_for_surface(surface: str) -> bool:
    """Internal helper for ml allowed for surface."""
    if not bool(getattr(settings, "RECOMMENDATION_ML_ENABLED", False)):
        return False
    allowed_surfaces = set(getattr(settings, "RECOMMENDATION_ML_SURFACES", []) or [])
    return bool(surface and surface in allowed_surfaces)
