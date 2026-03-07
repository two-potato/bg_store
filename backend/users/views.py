from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from .models import UserProfile
import json
import urllib.parse
import hmac
import hashlib
import time
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
from core.logging_utils import log_calls
import logging

log = logging.getLogger("users")

def verify_init_data(init_data: str) -> dict | None:
    try:
        bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        if not bot_token:
            log.warning("tg_init_data_missing_bot_token")
            return None
        parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
        received_hash = parsed.pop("hash", [None])[0]
        if not received_hash:
            log.warning("tg_init_data_missing_hash")
            return None
        data_check_string = "\n".join(f"{k}={','.join(v)}" for k,v in sorted(parsed.items()))
        secret_key = hashlib.sha256(("WebAppData" + bot_token).encode()).digest()
        h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(h, received_hash):
            log.warning("tg_init_data_hash_mismatch")
            return None
        auth_date_raw = parsed.get("auth_date", [None])[0]
        if not auth_date_raw:
            log.warning("tg_init_data_missing_auth_date")
            return None
        auth_date = int(auth_date_raw)
        max_age = int(getattr(settings, "TG_INIT_DATA_MAX_AGE_SECONDS", 300))
        now = int(time.time())
        if auth_date > now + 30 or (now - auth_date) > max_age:
            log.warning("tg_init_data_expired", extra={"auth_date": auth_date, "max_age": max_age})
            return None
        user_json = parsed.get("user", [None])[0]
        return json.loads(user_json) if user_json else {}
    except Exception:
        log.exception("tg_init_data_verify_error")
        return None

@api_view(["GET"])
@log_calls()
def me(request):
    prof = getattr(request.user, "profile", None)
    store = getattr(request.user, "seller_store", None)
    return Response({
        "username": request.user.username,
        "telegram_id": getattr(prof, "telegram_id", None),
        "discount": str(getattr(prof, "discount", 0)),
        "role": getattr(prof, "role", None),
        "seller_store": getattr(store, "name", None),
    })

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@log_calls()
def tg_webapp_auth(request):
    init_data = request.data.get("initData","")
    tg_user = verify_init_data(init_data)
    if tg_user is None:
        log.warning("tg_webapp_auth_invalid_init_data")
        return Response({"detail":"invalid initData"}, status=403)
    telegram_id = tg_user.get("id")
    try:
        telegram_id = int(telegram_id)
    except Exception:
        log.warning("tg_webapp_auth_missing_tg_id")
        return Response({"detail": "invalid telegram user id"}, status=403)
    username = tg_user.get("username") or f"tg_{telegram_id}"
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=f"tg_{telegram_id}")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.telegram_id = telegram_id
    profile.telegram_username = username
    profile.save()
    token = str(AccessToken.for_user(user))
    log.info("tg_webapp_auth_ok", extra={"user_id": user.id, "telegram_id": telegram_id})
    return Response({"access": token})
