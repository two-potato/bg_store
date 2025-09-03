import os
import hmac
import hashlib
SECRET = os.getenv("ORDER_APPROVE_SECRET","dev")

def sign_approve(order_id:int, admin_tg_id:int)->str:
    msg = f"{order_id}:{admin_tg_id}".encode()
    return hmac.new(SECRET.encode(), msg, hashlib.sha256).hexdigest()
