import time

from django.test import override_settings

from shopfront.recommendation import contracts as recommendation_contracts
from shopfront.searching import contracts as search_contracts


@override_settings(
    RECOMMENDATION_SERVICE_MODE="FASTAPI",
    RECOMMENDATION_SERVICE_URL="http://recommendation-api:8011/",
    RECOMMENDATION_SERVICE_TIMEOUT_SECONDS="1.25",
    SEARCH_SERVICE_MODE="FASTAPI",
    SEARCH_SERVICE_URL="http://search-api:8010/",
    SEARCH_SERVICE_TIMEOUT_SECONDS="1.5",
)
def test_contract_runtime_settings_helpers():
    assert recommendation_contracts._service_mode() == "fastapi"
    assert recommendation_contracts._service_url() == "http://recommendation-api:8011"
    assert recommendation_contracts._service_timeout() == 1.25
    assert search_contracts._service_mode() == "fastapi"
    assert search_contracts._service_url() == "http://search-api:8010"
    assert search_contracts._service_timeout() == 1.5

    contract_id = recommendation_contracts._new_contract_id()
    assert len(contract_id) == 32
    assert recommendation_contracts._elapsed_ms(time.perf_counter()) >= 0
