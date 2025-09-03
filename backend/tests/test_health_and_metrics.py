def test_health(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_metrics(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert b"python_info" in resp.content
