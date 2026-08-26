from __future__ import annotations

from django.core.cache import cache

from .models import FavoriteProduct


def favorites_cache_key(user_id: int) -> str:
    """Handle favorites cache key."""
    return f"shopfront:favorite_product_ids:v1:{int(user_id)}"


def session_cart_state(cart: dict) -> tuple[int, dict[int, int], list[int], int]:
    """Handle session cart state."""
    count = 0
    qty_map: dict[int, int] = {}
    ids: list[int] = []
    malformed = 0
    for raw_pid, payload in (cart or {}).items():
        try:
            pid = int(raw_pid)
            qty = max(0, int((payload or {}).get("qty", 0)))
        except (TypeError, ValueError, AttributeError):
            malformed += 1
            continue
        count += qty
        qty_map[pid] = qty
        if qty > 0:
            ids.append(pid)
    return count, qty_map, ids, malformed


def favorite_product_ids_for_user(user, *, limit: int = 2000) -> list[int]:
    """Handle favorite product ids for user."""
    if not getattr(user, "is_authenticated", False):
        return []
    cache_key = favorites_cache_key(user.id)
    favorite_ids = cache.get(cache_key)
    if favorite_ids is None:
        favorite_ids = list(
            FavoriteProduct.objects.filter(user=user).values_list("product_id", flat=True)[:limit]
        )
        cache.set(cache_key, favorite_ids, timeout=120)
    return favorite_ids
