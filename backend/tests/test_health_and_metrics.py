from django.test.utils import override_settings


def test_health(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@override_settings(DEBUG=True, METRICS_TOKEN="")
def test_metrics_public_in_debug(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"python_info" in resp.content


@override_settings(DEBUG=False, METRICS_TOKEN="metrics-secret")
def test_metrics_requires_token_in_non_debug(client):
    forbidden = client.get("/metrics")
    assert forbidden.status_code == 403

    ok = client.get("/metrics", HTTP_X_METRICS_TOKEN="metrics-secret")
    assert ok.status_code == 200
    assert b"python_info" in ok.content
