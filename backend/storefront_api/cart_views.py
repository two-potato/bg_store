from __future__ import annotations

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie

from catalog.models import Product
from commerce.cart_checkout import cart_badge_context
from commerce.cart_mutations import add_to_cart_session, clear_cart_session, remove_from_cart_session, update_cart_session
from commerce.cart_store import merge_session_cart_with_persistent

from .common import cart_payload, json_error, money, read_int, request_payload


@method_decorator(ensure_csrf_cookie, name="dispatch")
class StorefrontSessionBootstrapView(View):
    def get(self, request):
        if request.user.is_authenticated:
            request.session["cart"] = merge_session_cart_with_persistent(request.user, request.session.get("cart", {}))
            request.session.modified = True
        badge = cart_badge_context(request)
        user = request.user if request.user.is_authenticated else None
        profile = getattr(user, "profile", None) if user else None
        payload_user = None if user is None else {
            "id": user.id, "username": user.username, "email": user.email or "",
            "full_name": getattr(profile, "full_name", "") or user.get_full_name() or "",
            "phone": getattr(profile, "phone", "") or "", "contact_email": getattr(profile, "contact_email", "") or "",
            "role": getattr(profile, "role", None), "discount": money(getattr(profile, "discount", 0) or 0),
            "seller_store": {"id": getattr(getattr(user, "seller_store", None), "id", None), "name": getattr(getattr(user, "seller_store", None), "name", "") or "", "slug": getattr(getattr(user, "seller_store", None), "slug", "") or ""},
            "telegram": {"id": getattr(profile, "telegram_id", None), "username": getattr(profile, "telegram_username", "") or "", "linked": bool(getattr(profile, "telegram_id", None))},
        }
        response = JsonResponse({"ok": True, "session": {"authenticated": bool(user), "session_key": request.session.session_key or "", "csrf_token": get_token(request)}, "user": payload_user, "cart_badge": {"count": int(badge["count"]), "subtotal": money(badge["subtotal"])}, "urls": {"login": "/account/login/?next=/", "logout": "/account/logout/", "account": "/account/", "cart": "/cart/"}})
        response["Cache-Control"] = "no-store"
        response["Vary"] = "Cookie"
        return response


class StorefrontCartView(View):
    def get(self, request):
        return JsonResponse({"ok": True, "cart": cart_payload(request)})


class StorefrontCartAddView(View):
    def post(self, request):
        payload, error = request_payload(request)
        if error:
            return json_error(request, error, 400)
        product_id, qty = read_int(payload, "product_id"), read_int(payload, "qty", 1)
        if not product_id or qty is None:
            return json_error(request, "invalid_payload", 400)
        try:
            result = add_to_cart_session(request=request, product_id=product_id, qty=max(1, qty), logger=__import__("logging").getLogger("storefront_api"))
        except Product.DoesNotExist:
            return json_error(request, "product_not_found", 404)
        return JsonResponse({"ok": True, "item": {"product_id": product_id, "qty": int(result["current_qty"]), "line_value": money(result["line_value"])}, "cart": cart_payload(request)})


class StorefrontCartUpdateView(View):
    def post(self, request):
        payload, error = request_payload(request)
        if error:
            return json_error(request, error, 400)
        product_id = read_int(payload, "product_id")
        if not product_id:
            return json_error(request, "invalid_product", 400)
        op = str(payload.get("op") or "set").lower()
        result = update_cart_session(request=request, product_id=product_id, op=op if op in {"set", "inc", "dec"} else "set", requested_qty=payload.get("qty"), logger=__import__("logging").getLogger("storefront_api"))
        if result["missing"]:
            return json_error(request, "item_not_in_cart", 404)
        return JsonResponse({"ok": True, "item": {"product_id": product_id, "qty": int(result["qty"])}, "cart": cart_payload(request)})


class StorefrontCartRemoveView(View):
    def post(self, request):
        payload, error = request_payload(request)
        if error:
            return json_error(request, error, 400)
        product_id = read_int(payload, "product_id")
        if not product_id:
            return json_error(request, "invalid_product", 400)
        remove_from_cart_session(request=request, product_id=product_id)
        return JsonResponse({"ok": True, "cart": cart_payload(request)})


class StorefrontCartClearView(View):
    def post(self, request):
        clear_cart_session(request=request)
        return JsonResponse({"ok": True, "cart": cart_payload(request)})
