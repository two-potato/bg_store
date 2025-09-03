from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import permissions
from django.contrib.auth import get_user_model
from .models import UserProfile
import json, urllib.parse, hmac, hashlib, os
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken
from core.logging_utils import log_calls

def verify_init_data(init_data: str) -> dict | None:
    try:
        parsed = urllib.parse.parse_qs(init_data, keep_blank_values=True)
        received_hash = parsed.pop("hash", [None])[0]
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={','.join(v)}" for k,v in sorted(parsed.items()))
        secret_key = hashlib.sha256(("WebAppData" + settings.TELEGRAM_BOT_TOKEN).encode()).digest()
        h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if h != received_hash:
            return None
        user_json = parsed.get("user", [None])[0]
        return json.loads(user_json) if user_json else {}
    except Exception:
        return None

@api_view(["GET"])
@log_calls()
def me(request):
    prof = getattr(request.user, "profile", None)
    return Response({
        "username": request.user.username,
        "telegram_id": getattr(prof, "telegram_id", None),
        "discount": str(getattr(prof, "discount", 0)),
    })

@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@log_calls()
def tg_webapp_auth(request):
    init_data = request.data.get("initData","")
    tg_user = verify_init_data(init_data)
    if tg_user is None:
        return Response({"detail":"invalid initData"}, status=403)
    telegram_id = tg_user.get("id")
    username = tg_user.get("username") or f"tg_{telegram_id}"
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=f"tg_{telegram_id}")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.telegram_id = telegram_id
    profile.telegram_username = username
    profile.save()
    token = str(AccessToken.for_user(user))
    return Response({"access": token})
