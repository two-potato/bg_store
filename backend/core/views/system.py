import hmac

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, JsonResponse
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

from core.logging_utils import log_calls


def liveness_view(_request):
    return JsonResponse({"ok": True})


def readiness_view(_request):
    status = {"ok": True, "database": True, "cache": True}

    try:
        connection.ensure_connection()
    except Exception:
        status["database"] = False
        status["ok"] = False

    try:
        probe_key = "servio:readiness-probe"
        cache.set(probe_key, "ok", timeout=10)
        if cache.get(probe_key) != "ok":
            raise RuntimeError("cache readiness probe mismatch")
        cache.delete(probe_key)
    except Exception:
        status["cache"] = False
        status["ok"] = False

    return JsonResponse(status, status=200 if status["ok"] else 503)


@log_calls()
def metrics_view(request):
    if settings.DEBUG:
        return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)
    provided = (request.headers.get("X-Metrics-Token") or "").strip()
    expected = (getattr(settings, "METRICS_TOKEN", "") or "").strip()
    if not expected or not hmac.compare_digest(provided, expected):
        return HttpResponse("Forbidden", status=403)
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)
