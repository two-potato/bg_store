import os
import hmac
import hashlib

SECRET = os.getenv("ORDER_APPROVE_SECRET", "dev")

def sign_approve(order_id: int, admin_tg_id: int, ts: int | None = None) -> str:
    """HMAC signature for approve/reject callbacks.

    If ts is provided, it is included in the signed payload for replay protection.
    """
    if ts is None:
        msg = f"{order_id}:{admin_tg_id}".encode()
    else:
        msg = f"{order_id}:{admin_tg_id}:{ts}".encode()
    return hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
