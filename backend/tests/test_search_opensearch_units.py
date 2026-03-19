import pytest
import requests
from django.test import override_settings

from catalog import opensearch_index
from shopfront import search as sf_search

pytestmark = pytest.mark.django_db


class _Resp:
    def __init__(self, status_code=200, payload=None, fail=False):
        self.status_code = status_code
        self._payload = payload or {}
        self._fail = fail
        self.text = "err"

    def raise_for_status(self):
        if self._fail or self.status_code >= 400:
            raise requests.HTTPError("http fail")

    def json(self):
        return self._payload


@override_settings(OPENSEARCH_ENABLED=True)
def test_opensearch_search_bundle_success(monkeypatch):
    def _post(url, json, timeout):
        assert url.endswith('/products/_search')
        assert json['size'] == 3
        return _Resp(payload={
            'hits': {
                'hits': [
                    {'_source': {'id': 10}},
                    {'_id': '11'},
                    {'_source': {'id': 'bad'}},
                ]
            },
            "aggregations": {
                "country_suggestions_scope": {
                    "country_suggestions": {
                        "buckets": [{"key": "Италия"}, {"key": "Россия"}]
                    }
                }
            },
        })

    monkeypatch.setattr(sf_search.requests, 'post', _post)
    ids, countries, suggestions = sf_search._opensearch_search_bundle('abc', 3, 2)
    assert ids == [10, 11]
    assert countries == ["Италия", "Россия"]
    assert suggestions == []


def test_search_product_ids_es_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(sf_search, 'live_search_bundle', lambda query, limit, country_limit: ([], []))
    ids = sf_search.search_product_ids('lavazza', 8)
    assert ids == []


def test_search_product_ids_es_exception_returns_empty(monkeypatch):
    def _boom(*args, **kwargs):
        raise sf_search.OpenSearchUnavailable('down')

    monkeypatch.setattr(sf_search, 'live_search_bundle', _boom)
    ids = sf_search.search_product_ids('brazil', 8)
    assert ids == []


def test_popular_country_suggestions_from_bundle(monkeypatch):
    monkeypatch.setattr(
        sf_search,
        'live_search_bundle',
        lambda query, limit, country_limit: ([1], ["Италия", "Россия"]),
    )
    assert sf_search.popular_country_suggestions("it", 2) == ["Италия", "Россия"]


@override_settings(OPENSEARCH_ENABLED=True)
def test_opensearch_index_upsert_and_delete_success(monkeypatch):
    calls = []

    def _put(url, json, timeout):
        calls.append(('put', url, json, timeout))
        return _Resp(status_code=200)

    def _delete(url, timeout):
        calls.append(('delete', url, timeout))
        return _Resp(status_code=200)

    monkeypatch.setattr(opensearch_index.requests, 'put', _put)
    monkeypatch.setattr(opensearch_index.requests, 'delete', _delete)

    class _P:
        id = 77
        name = 'Prod'
        sku = '12345678'
        seller = type('S', (), {'username': 'seller'})()
        seller_store = None
        brand = type('B', (), {'name': 'Brand'})()
        category = type('C', (), {'name': 'Category'})()
        country_of_origin = type('Co', (), {'name': 'Italy'})()
        description = 'Desc'
        price = 15
        is_new = True

    opensearch_index.upsert_product(_P())
    opensearch_index.delete_product(77)

    assert calls[0][0] == 'put'
    assert calls[1][0] == 'delete'


def test_opensearch_index_delete_non_ok_raises_handled(monkeypatch):
    def _delete(url, timeout):
        return _Resp(status_code=500)

    monkeypatch.setattr(opensearch_index.requests, 'delete', _delete)
    opensearch_index.delete_product(99)


def test_opensearch_index_upsert_exception_handled(monkeypatch):
    def _put(url, json, timeout):
        raise requests.ConnectionError('boom')

    monkeypatch.setattr(opensearch_index.requests, 'put', _put)

    class _P:
        id = 1
        name = 'Prod'
        sku = '12345678'
        seller = None
        brand = None
        category = None
        country_of_origin = None
        description = ''
        price = 0
        is_new = False

    opensearch_index.upsert_product(_P())
