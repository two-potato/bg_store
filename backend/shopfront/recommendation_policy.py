from __future__ import annotations

import time


RECOMMENDATION_CONTROLS_SESSION_KEY = "shopfront_recommendation_controls_v1"
DISMISS_TTL_SECONDS = 60 * 60 * 24 * 14


def _now_ts() -> int:
    return int(time.time())


def _ensure_state(request) -> dict:
    state = request.session.get(RECOMMENDATION_CONTROLS_SESSION_KEY)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("dismissed", {})
    return state


def remember_recommendation_dismiss(request, *, surface: str, product_id: int) -> None:
    if product_id <= 0:
        return
    state = _ensure_state(request)
    dismissed = state.setdefault("dismissed", {})
    dismissed.setdefault(surface or "unknown", {})[str(product_id)] = _now_ts()
    request.session[RECOMMENDATION_CONTROLS_SESSION_KEY] = state
    request.session.modified = True


def dismissed_product_ids(request, *, surface: str = "", now_ts: int | None = None) -> set[int]:
    if request is None or not hasattr(request, "session"):
        return set()
    state = _ensure_state(request)
    current_ts = _now_ts() if now_ts is None else now_ts
    dismissed = state.get("dismissed", {}) or {}
    surface_keys = [key for key in {surface or "", "global"} if key]
    blocked: set[int] = set()
    for key in surface_keys:
        rows = dismissed.get(key, {}) or {}
        for product_id, ts in rows.items():
            try:
                pid = int(product_id)
                dismissed_ts = int(ts)
            except (TypeError, ValueError):
                continue
            if pid <= 0:
                continue
            if dismissed_ts > 0 and (current_ts - dismissed_ts) <= DISMISS_TTL_SECONDS:
                blocked.add(pid)
    return blocked
