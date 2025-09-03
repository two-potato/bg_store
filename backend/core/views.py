from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest, REGISTRY
from core.logging_utils import log_calls

@log_calls()
def metrics_view(_):
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)
