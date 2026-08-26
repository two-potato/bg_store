from catalog.models import normalize_public_media_url


def test_normalize_public_media_url_rewrites_legacy_public_media_host():
    value = "https://complaexbar.ru/media/complaexbar/products/SC000031.png"

    assert normalize_public_media_url(value) == "/media/complaexbar/products/SC000031.png"


def test_normalize_public_media_url_keeps_non_media_external_urls():
    value = "https://example.com/assets/product.png"

    assert normalize_public_media_url(value) == value
