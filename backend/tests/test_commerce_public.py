import pytest
from commerce.models import LegalEntity, LegalEntityMembership

pytestmark = pytest.mark.django_db


def test_check_inn(api_client, db):
    le = LegalEntity.objects.create(name="X", inn="7707083893", bik="044525225", checking_account="40702810900000000001")
    # exists
    r1 = api_client.post("/api/commerce/check-inn/", data={"inn": le.inn}, content_type="application/json")
    assert r1.status_code == 200 and r1.json()["exists"] is True
    # not exists
    r2 = api_client.post("/api/commerce/check-inn/", data={"inn": "1234567890"}, content_type="application/json")
    assert r2.status_code == 200 and r2.json()["exists"] is False


def test_membership_request_create_no_admins(monkeypatch, api_client, db):
    le = LegalEntity.objects.create(name="Y", inn="7728168971", bik="044525225", checking_account="40702810900000000002")
    r = api_client.post("/api/commerce/membership-requests/", data={"legal_entity": le.id})
    assert r.status_code == 201


def test_delivery_addresses_crud(api_client, user, db):
    le = LegalEntity.objects.create(name="Z", inn="5408131553", bik="044525225", checking_account="40702810900000000003")
    LegalEntityMembership.objects.create(user=user, legal_entity=le)
    # Create via API (perform_create binds legal_entity from request data)
    payload = {
        "label": "Office",
        "country": "RU",
        "city": "Moscow",
        "street": "Tverskaya",
        "postcode": "101000",
        "details": "",
        "is_default": True,
        "legal_entity": le.id,
    }
    r = api_client.post("/api/commerce/delivery-addresses/", data=payload)
    assert r.status_code == 201
    # List filtered by legal_entity
    r2 = api_client.get(f"/api/commerce/delivery-addresses/?legal_entity={le.id}")
    assert r2.status_code == 200 and len(r2.json()) == 1


def test_lookup_endpoints(monkeypatch, api_client):
    # Mock AsyncClient to avoid real HTTP
    class FakeResponse:
        def __init__(self, data): self._data = data
        def raise_for_status(self): pass
        def json(self): return self._data

    class FakeAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def post(self, url, json=None, headers=None):
            if "party" in url:
                return FakeResponse({"suggestions": [{"data": {"inn": "7707083893","kpp": "770701001","ogrn":"1027700132195","name":{"short_with_opf":"ООО Тест"},"address":{"unrestricted_value":"Москва","data":{"street_with_type":"ул Пушкина","house":"1"}}}}]})
            if "bank" in url:
                return FakeResponse({"suggestions": [{"data": {"bic":"044525225","name":{"payment":"СБЕР"},"corr_account":"30101810400000000225","address":{"value":"Москва"}}}]})
            return FakeResponse({"suggestions": []})

    import httpx
    from commerce import views_public as vpub
    # Ensure token gate passes
    monkeypatch.setattr(vpub, "DADATA_TOKEN", "x")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    # party by inn
    r1 = api_client.get("/api/commerce/lookup/party/?inn=7707083893")
    assert r1.status_code == 200 and r1.json()["inn"] == "7707083893"
    # bank by bik
    r2 = api_client.get("/api/commerce/lookup/bank/?bik=044525225")
    assert r2.status_code == 200 and r2.json()["bik"] == "044525225"
    # preview HTML
    r3 = api_client.get("/api/commerce/lookup/party_preview/?inn=7707083893")
    assert r3.status_code == 200 and len(r3.content) > 0
    # reverse geocode path uses separate util; simulate 404
    # Reverse geocode success path by monkeypatching util
    from commerce import views_public as vpub
    monkeypatch.setattr(vpub, "reverse_geocode", lambda a,b: {"country":"RU","city":"Msk","street":"Lenina","postcode":"101000"})
    r4 = api_client.get("/api/commerce/lookup/revgeo/?lat=1&lon=2")
    assert r4.status_code == 200

    # Preview 404 path
    class FakeEmptyAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            class R: 
                def raise_for_status(self): pass
                def json(self): return {"suggestions": []}
            return R()
    monkeypatch.setattr(httpx, "AsyncClient", FakeEmptyAsyncClient)
    r5 = api_client.get("/api/commerce/lookup/party_preview/?inn=000")
    assert r5.status_code == 404

    # Preview exception path -> 500
    class FakeErrAsyncClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw):
            raise RuntimeError("boom")
    monkeypatch.setattr(httpx, "AsyncClient", FakeErrAsyncClient)
    r6 = api_client.get("/api/commerce/lookup/party_preview/?inn=111")
    assert r6.status_code == 500
