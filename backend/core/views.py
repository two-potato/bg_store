import hmac
import ipaddress
from django.http import HttpResponse
from django.conf import settings
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY
from core.logging_utils import log_calls

@log_calls()
def metrics_view(request):
    if not settings.DEBUG:
        remote_addr = (request.META.get("REMOTE_ADDR") or "").strip()
        try:
            remote_ip = ipaddress.ip_address(remote_addr) if remote_addr else None
        except ValueError:
            remote_ip = None
        if remote_ip and (remote_ip.is_loopback or remote_ip.is_private):
            return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)
        provided = (request.headers.get("X-Metrics-Token") or "").strip()
        expected = (getattr(settings, "METRICS_TOKEN", "") or "").strip()
        if not expected or not hmac.compare_digest(provided, expected):
            return HttpResponse("Forbidden", status=403)
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)
