from django.urls import Resolver404, resolve


PUBLIC_API_PATHS = (
    "/api/search/query/",
    "/api/search/suggestions/",
    "/api/recommendations/home/",
    "/api/recommendations/cart/",
    "/api/recommendations/checkout/",
    "/api/recommendations/reorder/",
    "/api/recommendations/search-recovery/",
)


def _resolved_module(path: str) -> str:
    match = resolve(path)
    view_class = getattr(match.func, "view_class", None)
    if view_class is not None:
        return view_class.__module__
    return match.func.__module__


def test_public_storefront_api_is_not_owned_by_shopfront_app():
    modules = {_resolved_module(path) for path in PUBLIC_API_PATHS}

    assert modules
    assert all(not module.startswith("shopfront.") for module in modules)


def test_django_does_not_serve_customer_storefront_root():
    try:
        match = resolve("/")
    except Resolver404:
        return

    module = getattr(getattr(match.func, "view_class", None), "__module__", match.func.__module__)
    assert not module.startswith("shopfront.")
