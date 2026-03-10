from .models import PersistentCart


def sanitize_cart_payload(raw_payload) -> dict[str, dict]:
    cleaned: dict[str, dict] = {}
    if not isinstance(raw_payload, dict):
        return cleaned
    for raw_pid, payload in raw_payload.items():
        try:
            pid = int(raw_pid)
            qty = max(0, int((payload or {}).get("qty", 0)))
        except Exception:
            continue
        if pid <= 0 or qty <= 0:
            continue
        cleaned[str(pid)] = {"qty": qty}
    return cleaned


def persist_cart_for_user(user, session_cart) -> None:
    if not user or not getattr(user, "is_authenticated", False):
        return
    payload = sanitize_cart_payload(session_cart)
    PersistentCart.objects.update_or_create(
        user=user,
        defaults={"payload": payload},
    )


def merge_session_cart_with_persistent(user, session_cart) -> dict[str, dict]:
    persistent, _created = PersistentCart.objects.get_or_create(user=user, defaults={"payload": {}})
    merged = sanitize_cart_payload(persistent.payload)
    for pid, payload in sanitize_cart_payload(session_cart).items():
        existing = max(0, int((merged.get(pid) or {}).get("qty", 0)))
        incoming = max(0, int((payload or {}).get("qty", 0)))
        merged[pid] = {"qty": max(existing, incoming)}
    persistent.payload = merged
    persistent.save(update_fields=["payload", "updated_at"])
    return merged
