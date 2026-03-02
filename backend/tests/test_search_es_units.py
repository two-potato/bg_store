import pytest

from catalog.models import Brand, Category, Country, Product
from catalog import es_index
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
            raise RuntimeError("http fail")

    def json(self):
        return self._payload


def test_es_search_ids_success(monkeypatch):
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
            }
        })

    monkeypatch.setattr(sf_search.requests, 'post', _post)
    assert sf_search._es_search_ids('abc', 3) == [10, 11]


def test_search_product_ids_es_empty_returns_empty(monkeypatch):
    monkeypatch.setattr(sf_search, '_es_search_ids', lambda query, limit: [])
    ids = sf_search.search_product_ids('lavazza', 8)
    assert ids == []


def test_search_product_ids_es_exception_returns_empty(monkeypatch):
    def _boom(*args, **kwargs):
        raise sf_search.ESSearchUnavailable('down')

    monkeypatch.setattr(sf_search, '_es_search_ids', _boom)
    ids = sf_search.search_product_ids('brazil', 8)
    assert ids == []


def test_es_index_upsert_and_delete_success(monkeypatch):
    calls = []

    def _put(url, json, timeout):
        calls.append(('put', url, json, timeout))
        return _Resp(status_code=200)

    def _delete(url, timeout):
        calls.append(('delete', url, timeout))
        return _Resp(status_code=200)

    monkeypatch.setattr(es_index.requests, 'put', _put)
    monkeypatch.setattr(es_index.requests, 'delete', _delete)

    class _P:
        id = 77
        name = 'Prod'
        sku = '12345678'
        brand = type('B', (), {'name': 'Brand'})()
        category = type('C', (), {'name': 'Category'})()
        country_of_origin = type('Co', (), {'name': 'Italy'})()
        description = 'Desc'
        price = 15
        is_new = True

    es_index.upsert_product(_P())
    es_index.delete_product(77)

    assert calls[0][0] == 'put'
    assert calls[1][0] == 'delete'


def test_es_index_delete_non_ok_raises_handled(monkeypatch):
    def _delete(url, timeout):
        return _Resp(status_code=500)

    monkeypatch.setattr(es_index.requests, 'delete', _delete)
    es_index.delete_product(99)


def test_es_index_upsert_exception_handled(monkeypatch):
    def _put(url, json, timeout):
        raise RuntimeError('boom')

    monkeypatch.setattr(es_index.requests, 'put', _put)

    class _P:
        id = 1
        name = 'Prod'
        sku = '12345678'
        brand = None
        category = None
        country_of_origin = None
        description = ''
        price = 0
        is_new = False

    es_index.upsert_product(_P())
