"""Small view mixins for shopfront HTML/JSON interaction contracts."""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth.mixins import AccessMixin
from django.http import JsonResponse


def expects_json_response(request) -> bool:
    """Handle expects json response."""
    accept = (request.headers.get("Accept") or "").lower()
    requested_with = (request.headers.get("X-Requested-With") or "").lower()
    fetch_mode = (request.headers.get("Sec-Fetch-Mode") or "").lower()
    return (
        request.headers.get("HX-Request") == "true"
        or "application/json" in accept
        or requested_with == "xmlhttprequest"
        or fetch_mode == "cors"
    )


class JsonLoginRequiredMixin(AccessMixin):
    """Return JSON 401 for fetch-style requests instead of redirecting to HTML login."""

    def handle_no_permission(self):
        request = self.request
        if expects_json_response(request):
            next_target = request.get_full_path() or "/"
            login_url = f"{self.get_login_url()}?{urlencode({'next': next_target})}"
            return JsonResponse(
                {
                    "ok": False,
                    "error": "authentication_required",
                    "login_url": login_url,
                },
                status=401,
            )
        return super().handle_no_permission()
