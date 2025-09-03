from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

def health(_): return JsonResponse({"ok": True})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health),
    path("metrics", include("core.metrics_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
    path("api/users/", include("users.urls")),
    path("account/", include("users.urls_html")),
    path("api/commerce/", include("commerce.urls_public")),
    path("api/commerce/", include("commerce.urls_admin")),
    path("api/catalog/", include("catalog.urls")),
    path("api/orders/", include("orders.urls")),
    path("", include("shopfront.urls")),
]
