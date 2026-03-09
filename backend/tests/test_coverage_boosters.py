import asyncio
import logging
import smtplib
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.contrib.sessions.middleware import SessionMiddleware

from catalog.models import Brand, Category, Collection, Product, SellerInventory, SellerOffer
from commerce.company_service import (
    approver_memberships_for_company,
    ensure_approval_policy,
    resolve_order_approval_requirement,
    sync_company_membership_from_legal_entity,
)
from commerce.models import CompanyMembership, LegalEntity, LegalEntityMembership, MembershipRole, SellerStore
from core import notifications, sentry as sentry_runtime
from core.middleware import RequestContextMiddleware, RequestLoggingMiddleware
from orders import signals as order_signals
from orders.models import Order, OrderItem, SellerOrder
from orders.services import mark_seller_order_status, plan_seller_splits
from shopfront import cart_checkout_service
from shopfront import cart_mutation_service
from shopfront import recommendations
from shopfront import search as sf_search
from shopfront import tasks as shopfront_tasks
from shopfront.cart_store import merge_session_cart_with_persistent, persist_cart_for_user, sanitize_cart_payload
from shopfront.live_search_service import live_search_context
from shopfront.models import BrandSubscription, CategorySubscription, FavoriteProduct, RecentlyViewedProduct


pytestmark = pytest.mark.django_db


def _session_request(path="/"):
    factory = RequestFactory()
    request = factory.get(path)
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _catalog_fixture(prefix: str = "cov"):
    User = get_user_model()
    seller = User.objects.create_user(username=f"{prefix}_seller", password="pass")
    brand = Brand.objects.create(name=f"{prefix} brand")
    category = Category.objects.create(name=f"{prefix} category")
    seed = sum(ord(ch) for ch in prefix) % 90
    legal_entity = LegalEntity.objects.create(
        name=f"{prefix} le",
        inn=f"77070838{seed:02d}",
        bik="044525225",
        checking_account=f"4070281090000000{seed:04d}",
    )
    store = SellerStore.objects.create(owner=seller, legal_entity=legal_entity, name=f"{prefix} store")
    return seller, brand, category, store


class _Resp:
    def __init__(self, status_code=200, text="", payload=None, is_error=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}
        if is_error is not None:
            self.is_error = is_error

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def test_sentry_init_and_helpers(monkeypatch):
    assert sentry_runtime._env_bool("MISSING_FLAG", default=True) is True
    monkeypatch.delenv("EMPTY_FLOAT", raising=False)
    assert sentry_runtime._env_float("EMPTY_FLOAT", 2.5) == 2.5
    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    monkeypatch.delenv("APP_RELEASE", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("RELEASE_SHA", raising=False)
    assert sentry_runtime._release() is None
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "staging")
    assert sentry_runtime._environment(default_debug=False) == "staging"
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    sentry_runtime._INITIALIZED_SERVICES.clear()
    assert sentry_runtime.init_sentry(service_name="backend") is False

    monkeypatch.setenv("SENTRY_DSN", "https://dsn.example/1")
    monkeypatch.setenv("DEBUG", "1")
    monkeypatch.setenv("APP_RELEASE", "rel-1")
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "no")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.5")
    monkeypatch.setenv("SENTRY_PROFILES_SAMPLE_RATE", "0.2")
    monkeypatch.setenv("SENTRY_MAX_REQUEST_BODY_SIZE", "always")

    called = {}

    def _fake_init(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(sentry_runtime.sentry_sdk, "init", _fake_init)
    sentry_runtime._INITIALIZED_SERVICES.clear()

    assert sentry_runtime._env_bool("DEBUG") is True
    monkeypatch.setenv("BAD_FLOAT", "boom")
    assert sentry_runtime._env_float("BAD_FLOAT", 1.5) == 1.5
    assert sentry_runtime._release() == "rel-1"
    assert sentry_runtime._environment(default_debug=True) == "development"

    assert sentry_runtime.init_sentry(service_name="backend", enable_django=True, enable_celery=True) is True
    assert called["dsn"] == "https://dsn.example/1"
    assert called["server_name"] == "backend"
    assert called["release"] == "rel-1"
    assert called["environment"] == "development"
    assert called["send_default_pii"] is False
    assert called["traces_sample_rate"] == 0.5
    assert called["profiles_sample_rate"] == 0.2
    assert called["max_request_body_size"] == "always"
    assert len(called["integrations"]) == 3
    assert sentry_runtime.init_sentry(service_name="backend") is True


@override_settings(
    BOT_NOTIFY_URL="http://notify-bot:8080",
    INTERNAL_TOKEN="secret",
    ADMIN_NOTIFY_EMAILS=[" a@example.com ", "b@example.com", "a@example.com"],
    ADMIN_NOTIFY_TELEGRAM_IDS=[123, "456", "bad", 0],
)
def test_notifications_branches(monkeypatch):
    cache.clear()
    logger = logging.getLogger("test.notifications")
    assert notifications.notify_headers()["X-Internal-Token"] == "secret"
    assert notifications._response_is_error(type("R", (), {"status_code": 503})()) is True
    assert notifications._response_excerpt(type("R", (), {"text": "abcdef"})(), limit=3) == "abc"

    user = get_user_model().objects.create_user(username="notif_admin", password="pass")
    profile = user.profile
    profile.role = profile.Role.ADMIN
    profile.telegram_id = 789
    profile.save(update_fields=["role", "telegram_id"])
    notifications.quarantine_telegram_recipient(456, "blocked", ttl=10)

    assert notifications.admin_emails() == ["a@example.com", "b@example.com"]
    assert notifications.admin_telegram_ids() == [123, 789]

    mail_calls = []

    def _send_mail(**kwargs):
        mail_calls.append(kwargs)
        return 1

    monkeypatch.setattr(notifications, "send_mail", _send_mail)
    assert notifications.send_mail_message(subject="Subj", message="Body", recipient_list=[" a@e.com ", ""]) is True
    assert mail_calls[0]["recipient_list"] == ["a@e.com"]
    assert notifications.send_mail_message(subject="Subj", message="Body", recipient_list=[]) is False

    def _raise_transport(**kwargs):
        raise smtplib.SMTPException("smtp down")

    monkeypatch.setattr(notifications, "send_mail", _raise_transport)
    assert notifications.send_mail_message(subject="Subj", message="Body", recipient_list=["a@e.com"]) is False

    def _raise_unexpected(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(notifications, "send_mail", _raise_unexpected)
    assert notifications.send_mail_message(subject="Subj", message="Body", recipient_list=["a@e.com"]) is False

    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json, headers):
            if url.endswith("/notify/send_group"):
                return _Resp(payload={"ok": True})
            return _Resp(status_code=403, text="Bot was blocked by the user", is_error=True)

    monkeypatch.setattr(notifications.httpx, "Client", lambda timeout: _Client(timeout))
    ok, _ = notifications.post_notify_json(
        "/notify/send_group",
        {"text": "hello"},
        success_event="notify_ok",
        logger=logger,
    )
    assert ok is True
    assert notifications._should_quarantine_telegram_recipient("/notify/send_text", _Resp(status_code=403, text="user is deactivated"), {"telegram_id": 1}) is True
    assert notifications._should_quarantine_telegram_recipient("/notify/send_group", _Resp(status_code=403, text="chat not found"), {"telegram_id": 1}) is False
    assert notifications._should_quarantine_telegram_recipient("/notify/send_text", _Resp(status_code=200, text="chat not found"), {"telegram_id": 1}) is False
    assert notifications._should_quarantine_telegram_recipient("/notify/send_text", _Resp(status_code=403, text="chat not found"), {"telegram_id": None}) is False
    assert notifications.send_telegram_group("hello") is True
    assert notifications.send_telegram_text(555, "hello") is False
    assert notifications.is_telegram_recipient_quarantined(555) is True
    assert notifications.send_telegram_text(555, "hello again") is False

    monkeypatch.setattr(notifications, "admin_emails", lambda: ["fallback@example.com"])
    monkeypatch.setattr(notifications, "send_mail_message", lambda **kwargs: kwargs["recipient_list"] == ["fallback@example.com"])
    assert notifications.send_email_notification("Subj", "Body") is True
    monkeypatch.undo()
    monkeypatch.setattr(notifications.settings, "BOT_NOTIFY_URL", "http://notify-bot:8080", raising=False)
    monkeypatch.setattr(notifications.settings, "INTERNAL_TOKEN", "secret", raising=False)
    monkeypatch.setattr(notifications.settings, "ADMIN_NOTIFY_EMAILS", [], raising=False)
    monkeypatch.setattr(notifications.settings, "ADMINS", [("Ops", "ops@example.com")], raising=False)
    assert notifications.admin_emails() == ["ops@example.com"]

    monkeypatch.setattr(notifications, "send_telegram_text", lambda telegram_id, text: telegram_id == 777)
    assert notifications.send_telegram_bulk("hello", recipients=[777, 778]) == 1
    monkeypatch.setattr(notifications, "send_telegram_text", lambda telegram_id, text: False)
    assert notifications.send_telegram_bulk("hello", recipients=[777]) == 0

    monkeypatch.setattr(notifications, "post_notify_json", lambda *args, **kwargs: (True, _Resp(payload={"ok": False})))
    assert notifications.send_telegram_group("hello") is False
    monkeypatch.setattr(notifications, "post_notify_json", lambda *args, **kwargs: (True, _Resp(payload=None)))
    assert notifications.send_telegram_group("hello") is False
    monkeypatch.setattr(notifications, "post_notify_json", lambda *args, **kwargs: (False, None))
    assert notifications.send_telegram_group("hello") is False


@override_settings(BOT_NOTIFY_URL="http://notify-bot:8080", INTERNAL_TOKEN="secret")
def test_async_notify_and_notify_exceptions(monkeypatch):
    class _AsyncClient:
        def __init__(self, resp=None, exc=None):
            self.resp = resp
            self.exc = exc

        async def post(self, url, json, headers):
            if self.exc:
                raise self.exc
            return self.resp

    ok, resp = asyncio.run(
        notifications.apost_notify_json(
            _AsyncClient(resp=_Resp(status_code=200, payload={"ok": True}, is_error=False)),
            "/notify/send_text",
            {"telegram_id": 1, "text": "hi"},
            success_event="notify_async_ok",
        )
    )
    assert ok is True
    assert resp is not None

    ok, resp = asyncio.run(
        notifications.apost_notify_json(
            _AsyncClient(resp=_Resp(status_code=400, text="chat not found", is_error=True)),
            "/notify/send_text",
            {"telegram_id": 999, "text": "hi"},
            extra={"telegram_id": 999},
        )
    )
    assert ok is False
    assert resp is not None
    assert notifications.is_telegram_recipient_quarantined(999) is True

    ok, resp = asyncio.run(
        notifications.apost_notify_json(
            _AsyncClient(exc=RuntimeError("boom")),
            "/notify/send_text",
            {"telegram_id": 1, "text": "hi"},
        )
    )
    assert ok is False
    assert resp is None

    class _BoomClient:
        def __init__(self, timeout):
            raise RuntimeError("boom")

    monkeypatch.setattr(notifications.httpx, "Client", _BoomClient)
    ok, resp = notifications.post_notify_json("/notify/send_text", {"telegram_id": 1, "text": "x"})
    assert ok is False
    assert resp is None


def test_search_helpers_and_cache(monkeypatch, settings):
    settings.ES_ENABLED = True
    cache.clear()
    assert sf_search._normalize_bundle((["1"], ["IT"], ["cup"])) == (["1"], ["IT"], ["cup"])
    assert sf_search._normalize_bundle((["1"], ["IT"])) == (["1"], ["IT"], [])
    assert sf_search._normalize_bundle("bad") == ([], [], [])

    payload = sf_search._search_payload("  Ice   Tea ", 0, 0)
    assert payload["size"] == 1
    assert payload["suggest"]["query_suggest"]["prefix"] == "ice tea"

    settings.ES_ENABLED = False
    with pytest.raises(sf_search.ESSearchUnavailable):
        sf_search._es_search_bundle("cup", 2, 2)
    settings.ES_ENABLED = True

    def _post(url, json, timeout):
        return _Resp(
            payload={
                "hits": {"hits": [{"_source": {"id": 1}}, {"_id": "2"}, {"_source": {"id": "bad"}}]},
                "aggregations": {
                    "country_suggestions_scope": {"country_suggestions": {"buckets": [{"key": "IT"}, {"key": ""}]}}
                },
                "suggest": {
                    "query_suggest": [
                        {"options": [{"text": "Cup"}, {"text": "cup"}, {"text": " Mug "}, {"text": ""}]}
                    ]
                },
            }
        )

    monkeypatch.setattr(sf_search.requests, "post", _post)
    ids, countries, suggestions = sf_search._es_search_bundle("cup", 5, 2)
    assert ids == [1, 2]
    assert countries == ["IT"]
    assert suggestions == ["Cup", "Mug"]

    cached = sf_search.live_search_bundle("cup", limit=5, country_limit=0)
    assert cached == ([1, 2], [], ["Cup", "Mug"])
    monkeypatch.setattr(sf_search.requests, "post", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should not call")))
    assert sf_search.live_search_bundle("cup", limit=5, country_limit=0) == cached

    monkeypatch.setattr(sf_search.requests, "post", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")))
    with pytest.raises(sf_search.ESSearchUnavailable):
        sf_search._es_search_bundle("cup", 5, 1)


def test_recommendations_and_company_services():
    User = get_user_model()
    buyer = User.objects.create_user(username="cov_buyer", password="pass")
    approver = User.objects.create_user(username="cov_approver", password="pass")
    seller, brand, category, store = _catalog_fixture("cv")

    role_owner, _ = MembershipRole.objects.get_or_create(code="owner", defaults={"name": "Owner"})
    role_manager, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Manager"})
    lem = LegalEntityMembership.objects.create(legal_entity=store.legal_entity, user=buyer, role=role_manager)
    LegalEntityMembership.objects.create(legal_entity=store.legal_entity, user=approver, role=role_owner)
    membership = sync_company_membership_from_legal_entity(lem)
    assert membership.role == CompanyMembership.Role.BUYER

    company = membership.company
    policy = ensure_approval_policy(company)
    policy.is_enabled = True
    policy.auto_approve_below = Decimal("100.00")
    policy.save(update_fields=["is_enabled", "auto_approve_below"])

    decision = resolve_order_approval_requirement(legal_entity=store.legal_entity, user=buyer, order_total=Decimal("500.00"))
    assert decision.requires_approval is True
    assert "согласование" in decision.reason.lower()
    approver_decision = resolve_order_approval_requirement(legal_entity=store.legal_entity, user=approver, order_total=Decimal("500.00"))
    assert approver_decision.requires_approval is False
    no_auth = resolve_order_approval_requirement(legal_entity=store.legal_entity, user=None, order_total=Decimal("1.00"))
    assert no_auth.requires_approval is False
    auto_approved = resolve_order_approval_requirement(legal_entity=store.legal_entity, user=buyer, order_total=Decimal("50.00"))
    assert auto_approved.requires_approval is False
    outsider = User.objects.create_user(username="cov_outsider", password="pass")
    LegalEntityMembership.objects.create(legal_entity=store.legal_entity, user=outsider, role=role_manager)
    outsider_decision = resolve_order_approval_requirement(legal_entity=store.legal_entity, user=outsider, order_total=Decimal("500.00"))
    assert outsider_decision.membership is not None
    assert approver_memberships_for_company(company).count() >= 1

    p1 = Product.objects.create(sku="10000001", name="p1", brand=brand, category=category, price=10, stock_qty=3, seller=seller)
    p2 = Product.objects.create(sku="10000002", name="p2", brand=brand, category=category, price=11, stock_qty=3, seller=seller, is_new=True)
    p3 = Product.objects.create(sku="10000003", name="p3", brand=brand, category=category, price=12, stock_qty=3, seller=seller, is_promo=True)
    other_category = Category.objects.create(name="other cat")
    p4 = Product.objects.create(sku="10000004", name="p4", brand=brand, category=other_category, price=13, stock_qty=3, seller=seller)

    anon = type("Anon", (), {"is_authenticated": False})()
    recommendations.record_recent_view(anon, p1)
    assert recommendations.recently_viewed_ids_for_user(anon) == []

    recommendations.record_recent_view(buyer, p1, limit=2)
    recommendations.record_recent_view(buyer, p2, limit=2)
    recommendations.record_recent_view(buyer, p3, limit=2)
    assert recommendations.recently_viewed_ids_for_user(buyer, limit=2) == [p3.id, p2.id]
    assert RecentlyViewedProduct.objects.filter(user=buyer).count() == 2

    FavoriteProduct.objects.create(user=buyer, product=p1)
    BrandSubscription.objects.create(user=buyer, brand=brand)
    CategorySubscription.objects.create(user=buyer, category=other_category)
    sections = recommendations.personalized_home_sections(buyer, limit=10)
    assert p4.id in sections["brand_watch"]
    assert sections["based_on_lists"]

    assert recommendations.seller_cross_sell_ids(type("NoSeller", (), {"seller_id": None, "id": 1, "category_id": None})()) == []
    cross_sell_ids = recommendations.seller_cross_sell_ids(p1, limit=5)
    assert p4.id in cross_sell_ids
    assert p2.id not in cross_sell_ids

    order = Order.objects.create(placed_by=buyer)
    OrderItem.objects.create(order=order, product=p1, name=p1.name, price=p1.price, qty=1)
    OrderItem.objects.create(order=order, product=p4, name=p4.name, price=p4.price, qty=1)
    assert recommendations.frequently_bought_together_ids(p1, limit=5) == [p4.id]

    collection = Collection.objects.create(name="featured", slug="featured", is_active=True, is_featured=True)
    collection.products.add(p1)
    assert recommendations.featured_collection_ids(limit=5) == [collection.id]
    assert brand.id in recommendations.brand_highlight_ids(limit=5)


def test_cart_mutation_and_order_statuses(monkeypatch):
    User = get_user_model()
    buyer = User.objects.create_user(username="cart_buyer", password="pass")
    seller, brand, category, store = _catalog_fixture("ct")
    product = Product.objects.create(sku="20000001", name="prod", brand=brand, category=category, price=50, stock_qty=1, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=store, price=45, min_order_qty=1, lead_time_days=1)
    SellerInventory.objects.create(offer=offer, warehouse_name="main", stock_qty=4, reserved_qty=1, is_primary=True, eta_days=2)

    request = _session_request("/cart/")
    request.user = buyer
    logger = logging.getLogger("test.cart")

    payload = cart_mutation_service.add_to_cart_session(request=request, product_id=product.id, qty=5, logger=logger)
    assert payload["current_qty"] == 3
    assert str(payload["line_value"]) == "225.00"

    updated = cart_mutation_service.update_cart_session(request=request, product_id=product.id, op="set", requested_qty="bad", logger=logger)
    assert updated["qty"] == 3
    updated = cart_mutation_service.update_cart_session(request=request, product_id=product.id, op="set", requested_qty="9", logger=logger)
    assert updated["qty"] == 3
    updated = cart_mutation_service.update_cart_session(request=request, product_id=product.id, op="dec", requested_qty=None, logger=logger)
    assert updated["qty"] == 2
    cart_mutation_service.remove_from_cart_session(request=request, product_id=product.id)
    assert request.session["cart"] == {}
    missing = cart_mutation_service.update_cart_session(request=request, product_id=product.id, op="inc", requested_qty=None, logger=logger)
    assert missing["missing"] is True
    cart_mutation_service.clear_cart_session(request=request)
    assert request.session["cart"] == {}

    monkeypatch.setattr(cart_mutation_service, "_load_cart_product", lambda product_id: (_ for _ in ()).throw(Product.DoesNotExist()))
    request.session["cart"] = {str(product.id): {"qty": 1}}
    missing_product = cart_mutation_service.update_cart_session(request=request, product_id=product.id, op="inc", requested_qty=None, logger=logger)
    assert missing_product["product"] is None

    zero_stock = type("P", (), {"display_stock_qty": 0, "display_price": Decimal("10.00")})()
    monkeypatch.setattr(cart_mutation_service, "_load_cart_product", lambda product_id: zero_stock)
    request.session["cart"] = {}
    zero_payload = cart_mutation_service.add_to_cart_session(request=request, product_id=product.id, qty=1, logger=logger)
    assert zero_payload["current_qty"] == 1

    order = Order.objects.create(placed_by=buyer)
    OrderItem.objects.create(order=order, product=product, seller_offer=offer, name=product.name, price=offer.price, qty=1)
    plan_seller_splits(order)
    seller_order = SellerOrder.objects.get(order=order, seller=seller)
    mark_seller_order_status(seller_order, SellerOrder.Status.ACCEPTED)
    mark_seller_order_status(seller_order, SellerOrder.Status.SHIPPED)
    mark_seller_order_status(seller_order, SellerOrder.Status.DELIVERED)
    seller_order.refresh_from_db()
    assert seller_order.accepted_at is not None
    assert seller_order.shipped_at is not None
    assert seller_order.delivered_at is not None

    second_seller = User.objects.create_user(username="cart_seller_2", password="pass")
    second_store = SellerStore.objects.create(
        owner=second_seller,
        legal_entity=LegalEntity.objects.create(
            name="second le",
            inn="7707083812",
            bik="044525225",
            checking_account="40702810900000001234",
        ),
        name="second store",
    )
    second_product = Product.objects.create(
        sku="20000002",
        name="prod-2",
        brand=brand,
        category=category,
        price=60,
        stock_qty=1,
        seller=second_seller,
    )
    second_offer = SellerOffer.objects.create(product=second_product, seller=second_seller, seller_store=second_store, price=55)
    SellerInventory.objects.create(offer=second_offer, warehouse_name="w2", stock_qty=2, reserved_qty=0, is_primary=True, eta_days=1)
    multi_order = Order.objects.create(placed_by=buyer)
    OrderItem.objects.create(order=multi_order, product=product, seller_offer=offer, name=product.name, price=offer.price, qty=1)
    OrderItem.objects.create(order=multi_order, product=second_product, seller_offer=second_offer, name=second_product.name, price=second_offer.price, qty=1)
    plan_seller_splits(multi_order)
    multi_order.refresh_from_db()
    assert multi_order.split_status == Order.SplitStatus.PLANNED


def test_cart_checkout_store_and_middleware(monkeypatch):
    User = get_user_model()
    user = User.objects.create_user(username="svc_user", password="pass")
    seller, brand, category, store = _catalog_fixture("svc")
    product = Product.objects.create(sku="30000001", name="svc-prod", brand=brand, category=category, price=20, stock_qty=1, seller=seller)
    offer = SellerOffer.objects.create(product=product, seller=seller, seller_store=store, price=15, min_order_qty=1)
    SellerInventory.objects.create(offer=offer, warehouse_name="w1", stock_qty=8, reserved_qty=3, is_primary=True, eta_days=4)

    request = _session_request("/checkout/")
    request.user = user
    request.session["cart"] = {"bad": {"qty": 1}, str(product.id): {"qty": "2"}}
    user.profile.discount = Decimal("250.00")
    user.profile.save(update_fields=["discount"])

    monkeypatch.setattr(
        cart_checkout_service,
        "resolve_checkout_discount",
        lambda **kwargs: type(
            "DiscountResult",
            (),
            {
                "total_discount_amount": Decimal("5.00"),
                "coupon_discount_amount": Decimal("2.00"),
                "profile_discount_amount": Decimal("3.00"),
                "error": "",
                "coupon": None,
            },
        )(),
    )
    summary = cart_checkout_service.cart_summary(request)
    assert summary["cart_count"] == 2
    assert str(summary["subtotal"]) == "30.00"
    assert cart_checkout_service.profile_discount_percent(request) == Decimal("100.00")
    fake_profile_req = type(
        "Req",
        (),
        {
            "user": type(
                "User",
                (),
                {"is_authenticated": True, "profile": type("Profile", (), {"discount": "bad"})(), "get_full_name": lambda self: "", "username": "u", "email": ""},
            )()
        },
    )()
    assert cart_checkout_service.profile_discount_percent(fake_profile_req) == Decimal("0.00")
    negative_profile_req = type(
        "Req",
        (),
        {"user": type("User", (), {"is_authenticated": True, "profile": type("Profile", (), {"discount": Decimal("-5.00")})()})()},
    )()
    assert cart_checkout_service.profile_discount_percent(negative_profile_req) == Decimal("0.00")
    assert cart_checkout_service.checkout_identity_defaults(type("Req", (), {"user": type("Anon", (), {"is_authenticated": False})()})()) == ("", "")
    assert list(cart_checkout_service.checkout_addresses_queryset(type("Req", (), {"user": type("Anon", (), {"is_authenticated": False})()})())) == []
    assert cart_checkout_service.checkout_cart_tracking_payload({"items": []}, lambda *args, **kwargs: {}) == "{}"
    request.session["cart"]["999999"] = {"qty": 2}
    request.session["cart"]["oops"] = {"qty": "bad"}
    badge = cart_checkout_service.cart_badge_context(request)
    assert badge["count"] == 5

    company = sync_company_membership_from_legal_entity(
        LegalEntityMembership.objects.create(
            legal_entity=store.legal_entity,
            user=user,
            role=MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Manager"})[0],
        )
    ).company
    company_rows = cart_checkout_service.checkout_company_snapshots(
        request,
        [type("Membership", (), {"legal_entity": store.legal_entity, "legal_entity_id": store.legal_entity_id})()],
    )
    assert company_rows[0]["company"] == company
    assert company_rows[0]["policy"] is not None

    assert sanitize_cart_payload({"0": {"qty": 1}, "10": {"qty": "2"}, "bad": {"qty": 3}}) == {"10": {"qty": 2}}
    persist_cart_for_user(type("Anon", (), {"is_authenticated": False})(), {"10": {"qty": 1}})
    persist_cart_for_user(user, {"10": {"qty": 2}})
    merged = merge_session_cart_with_persistent(user, {"10": {"qty": 1}, "11": {"qty": 3}})
    assert merged == {"10": {"qty": 2}, "11": {"qty": 3}}
    assert sanitize_cart_payload("bad") == {}

    response = type("Resp", (dict,), {"status_code": 200})()
    captured = {}
    monkeypatch.setattr("core.middleware.set_request_context", lambda req: "rid-1")
    monkeypatch.setattr("core.middleware.clear_request_context", lambda: captured.setdefault("cleared", True))
    ctx_mw = RequestContextMiddleware(lambda req: response)
    result = ctx_mw(type("Req", (), {"path": "/x", "method": "GET"})())
    assert result["X-Request-ID"] == "rid-1"
    assert captured["cleared"] is True

    bad_response = object()
    ctx_mw_bad = RequestContextMiddleware(lambda req: bad_response)
    assert ctx_mw_bad(type("Req", (), {"path": "/x", "method": "GET"})()) is bad_response

    req_log_messages = []

    class _ReqLogger:
        def info(self, *args, **kwargs):
            req_log_messages.append(args)

    monkeypatch.setattr("core.middleware.request_logger", _ReqLogger())
    log_mw = RequestLoggingMiddleware(lambda req: type("Resp", (), {"status_code": 204})())
    result = log_mw(type("Req", (), {"path": "/ping", "method": "POST"})())
    assert result.status_code == 204
    assert len(req_log_messages) == 2


@override_settings(ADMIN_NOTIFY_EMAILS=[], ADMINS=[("Admin", "root@example.com")], ADMIN_NOTIFY_TELEGRAM_IDS=["700", "bad"])
def test_shopfront_tasks_and_live_search(monkeypatch):
    User = get_user_model()
    user = User.objects.create_user(username="task_admin", password="pass")
    user.profile.role = user.profile.Role.ADMIN
    user.profile.telegram_id = 701
    user.profile.save(update_fields=["role", "telegram_id"])

    monkeypatch.setattr(shopfront_tasks, "is_telegram_recipient_quarantined", lambda tg_id: tg_id == 701)
    assert shopfront_tasks._admin_emails() == ["root@example.com"]
    assert shopfront_tasks._admin_telegram_ids() == [700]
    user.profile.telegram_id = None
    user.profile.save(update_fields=["telegram_id"])
    monkeypatch.setattr(shopfront_tasks, "is_telegram_recipient_quarantined", lambda tg_id: False)
    assert shopfront_tasks._admin_telegram_ids() == [700]

    mail_calls = []
    monkeypatch.setattr(shopfront_tasks, "send_mail_message", lambda **kwargs: mail_calls.append(kwargs) or True)

    async_calls = []

    async def _fake_apost_notify_json(client, path, payload, **kwargs):
        async_calls.append((path, payload))
        return True, _Resp(payload={"ok": True}, is_error=False)

    monkeypatch.setattr(shopfront_tasks, "apost_notify_json", _fake_apost_notify_json)

    class _AsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _AsyncClient)
    shopfront_tasks.notify_contact_feedback.run(name="Name", phone="+7000", message="Hello", source="web")
    assert mail_calls
    assert len(async_calls) == 2

    monkeypatch.setattr(shopfront_tasks, "send_mail_message", lambda **kwargs: False)
    monkeypatch.setattr(shopfront_tasks, "_admin_emails", lambda: [])
    monkeypatch.setattr(shopfront_tasks, "apost_notify_json", _fake_apost_notify_json)
    shopfront_tasks.notify_contact_feedback.run(name="Name", phone="+7000", message="Hello", source="web")

    monkeypatch.setattr(shopfront_tasks, "apost_notify_json", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        shopfront_tasks.notify_contact_feedback.run(name="Name", phone="+7000", message="Hello", source="web")

    fallback_logger = logging.getLogger("test.live")
    assert live_search_context(query="ab", search_provider_getter=lambda: None, logger=fallback_logger)["show"] is False

    class _Bundle:
        product_ids = []
        countries = []
        suggestions = []

    class _Provider:
        def live_bundle(self, query, limit, country_limit):
            raise sf_search.ESSearchUnavailable("down")

    monkeypatch.setattr(
        "shopfront.live_search_service.DatabaseSearchProvider.live_bundle",
        lambda self, query, limit, country_limit: type("Bundle", (), {"product_ids": [], "countries": [], "suggestions": ["fallback"]})(),
    )
    monkeypatch.setattr("shopfront.live_search_service.suggest_query_corrections", lambda q, limit=6: ["corrected"])
    context = live_search_context(query="cup", search_provider_getter=lambda: _Provider(), logger=fallback_logger)
    assert context["show"] is True
    assert context["suggestions"]


def test_order_signal_helpers(monkeypatch):
    order = Order(id=123, status=Order.Status.NEW)

    class _Delay:
        def __init__(self, fail=False):
            self.fail = fail
            self.calls = []

        def delay(self, **kwargs):
            self.calls.append(kwargs)
            if self.fail:
                raise RuntimeError("boom")

    email = _Delay()
    tg = _Delay()
    monkeypatch.setattr(order_signals, "notify_admin_order_status_email", email)
    monkeypatch.setattr(order_signals, "notify_order_status_telegram", tg)
    order_signals._schedule_email(123, "created")
    order_signals._schedule_telegram_status(123, "created")
    assert email.calls and tg.calls

    monkeypatch.setattr(order_signals, "notify_admin_order_status_email", _Delay(fail=True))
    monkeypatch.setattr(order_signals, "notify_order_status_telegram", _Delay(fail=True))
    order_signals._schedule_email(123, "created")
    order_signals._schedule_telegram_status(123, "created")

    fresh = Order(status=Order.Status.NEW)
    order_signals.order_track_previous_status(Order, fresh)
    assert fresh._previous_status is None

    class _Manager:
        def only(self, *args, **kwargs):
            return self

        def get(self, pk):
            raise Order.DoesNotExist()

    monkeypatch.setattr(order_signals.Order, "objects", _Manager())
    existing = Order(id=999, status=Order.Status.NEW)
    order_signals.order_track_previous_status(Order, existing)
    assert existing._previous_status is None
