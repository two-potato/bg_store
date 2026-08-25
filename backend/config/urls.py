from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from core.views.system import liveness_view, readiness_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", liveness_view),
    path("ready/", readiness_view),
    path("metrics", include("core.metrics_urls")),
    path("api/users/", include("users.urls")),
    path("account/", include("users.urls_html")),
    path("api/commerce/", include("commerce.urls_public")),
    path("api/commerce/", include("commerce.urls_admin")),
    path("api/catalog/", include("catalog.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/", include("search_api.urls")),
    path("api/", include("recommendation_api.urls")),
    path("api/internal/", include("shopfront.api.internal_urls")),
    path("", include("storefront_api.urls")),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
