from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.db import models


_LOCAL_MEDIA_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"}
_PUBLIC_MEDIA_HOSTS = {"complaexbar.ru", "www.complaexbar.ru", "potatofarm.ru", "www.potatofarm.ru"}


def normalize_public_media_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    media_url = str(getattr(settings, "MEDIA_URL", "/media/") or "/media/")
    media_prefix = media_url if media_url.endswith("/") else f"{media_url}/"
    path = parts.path or "/"

    # Keep media references local when legacy imports stored absolute public hosts.
    if parts.scheme and parts.netloc and (parts.hostname or "").lower() in _PUBLIC_MEDIA_HOSTS and path.startswith(media_prefix):
        return urlunsplit(("", "", path, parts.query, parts.fragment))

    if parts.scheme and parts.netloc and (parts.hostname or "").lower() in _LOCAL_MEDIA_HOSTS:
        return urlunsplit(("", "", path, parts.query, parts.fragment))
    return raw


class SeoFieldsMixin(models.Model):
    """Reusable mixin to add SEO metadata to models."""

    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True
