import pytest
from django.test import override_settings
import yaml


pytestmark = pytest.mark.django_db


@override_settings(ENABLE_API_DOCS=True)
def test_openapi_schema_exposes_key_api_paths(client):
    response = client.get("/api/schema/")

    assert response.status_code == 200
    payload = yaml.safe_load(response.content.decode("utf-8"))
    paths = payload["paths"]

    assert "/api/users/me/" in paths
    assert "/api/catalog/products/" in paths
    assert "/api/commerce/delivery-addresses/" in paths
    assert "/api/orders/" in paths
    assert "/api/search/query/" in paths
    assert "/api/search/suggestions/" in paths
    assert "/api/recommendations/home/" in paths
    assert "/api/recommendations/cart/" in paths
    assert "/api/internal/search/query/" not in paths
    assert "/api/internal/recommendations/home/" not in paths
    assert "400" in paths["/api/orders/"]["post"]["responses"]
    assert "401" in paths["/api/orders/"]["post"]["responses"]
    assert "404" in paths["/api/orders/{id}/"]["get"]["responses"]
    assert "403" in paths["/api/commerce/delivery-addresses/"]["post"]["responses"]

    components = payload["components"]["schemas"]
    assert "ValidationError" in components
    assert "Жизненный цикл заказа" in yaml.safe_dump(components["Order"], allow_unicode=True)
    assert "Роль пользователя в системе" in yaml.safe_dump(components["Me"], allow_unicode=True)


@override_settings(ENABLE_API_DOCS=True)
def test_swagger_and_redoc_pages_render(client):
    swagger = client.get("/api/docs/")
    redoc = client.get("/api/redoc/")

    assert swagger.status_code == 200
    assert redoc.status_code == 200
    assert "SwaggerUIBundle" in swagger.content.decode("utf-8")
    assert "redoc.standalone" in redoc.content.decode("utf-8")
