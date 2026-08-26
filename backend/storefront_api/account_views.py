from __future__ import annotations

from decimal import Decimal

from django.http import JsonResponse
from django.views import View

from commerce.models import DeliveryAddress, LegalEntityCreationRequest, LegalEntityMembership
from legacy_shopfront_state.models import FavoriteProduct, SavedSearch
from orders.models import Order
from users.forms import AddressForm, NotificationPreferencesForm, ProfileForm
from users.models import UserProfile
from users.views.helpers import _company_workspace_rows, _notification_feed

from .common import coerce_bool, json_error, money, request_payload, string


def _profile_payload(profile: UserProfile) -> dict[str, object]:
    user = profile.user
    return {"full_name": profile.full_name or "", "contact_email": profile.contact_email or "", "phone": profile.phone or "", "photo_url": profile.photo.url if profile.photo else "", "username": user.username, "email": user.email or "", "role": profile.role, "discount": money(profile.discount or 0), "telegram": {"id": profile.telegram_id, "username": profile.telegram_username or "", "linked": bool(profile.telegram_id)}}


def _preferences(profile: UserProfile) -> dict[str, object]:
    return {"notify_email_orders": bool(profile.notify_email_orders), "notify_email_marketing": bool(profile.notify_email_marketing), "notify_telegram_orders": bool(profile.notify_telegram_orders), "notify_telegram_marketing": bool(profile.notify_telegram_marketing), "telegram_linked": bool(profile.telegram_id)}


def _address(address: DeliveryAddress) -> dict[str, object]:
    return {"id": address.id, "legal_entity": {"id": address.legal_entity_id, "name": address.legal_entity.name}, "label": address.label, "country": address.country, "city": address.city, "street": address.street, "postcode": address.postcode, "details": address.details or "", "latitude": float(address.latitude) if address.latitude is not None else None, "longitude": float(address.longitude) if address.longitude is not None else None, "is_default": bool(address.is_default), "updated_at": address.updated_at.isoformat()}


def _validation(form):
    return {"ok": False, "error": "validation_error", "fields": {field: [str(e) for e in errors] for field, errors in form.errors.items() if field != "__all__"}, "non_field_errors": [str(e) for e in form.non_field_errors()]}


def _user_payload(user) -> dict[str, object]:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    store = getattr(user, "seller_store", None)
    return {"id": user.id, "username": user.username, "email": user.email or "", "full_name": profile.full_name or user.get_full_name() or "", "phone": profile.phone or "", "contact_email": profile.contact_email or "", "role": profile.role, "discount": money(profile.discount or 0), "seller_store": {"id": getattr(store, "id", None), "name": getattr(store, "name", "") if store else "", "slug": getattr(store, "slug", "") if store else ""}, "telegram": {"id": profile.telegram_id, "username": profile.telegram_username or "", "linked": bool(profile.telegram_id)}}


def _order_short(order: Order) -> dict[str, object]:
    return {"id": order.id, "status": order.status, "status_display": order.get_status_display(), "approval_status": order.approval_status, "approval_status_display": order.get_approval_status_display(), "payment_method": order.payment_method, "delivery_method": order.delivery_method, "subtotal": money(order.subtotal), "discount_amount": money(order.discount_amount), "total": money(order.total), "created_at": order.created_at.isoformat(), "updated_at": order.updated_at.isoformat(), "legal_entity": {"id": order.legal_entity_id, "name": getattr(order.legal_entity, "name", "") if order.legal_entity_id else ""}, "detail_url": f"/account/orders/{order.id}/"}


class StorefrontAccountSettingsView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return JsonResponse({"ok": True, "settings": _profile_payload(profile)})
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = ProfileForm(data={"full_name": string(payload.get("full_name"), profile.full_name), "contact_email": string(payload.get("contact_email"), profile.contact_email), "phone": string(payload.get("phone"), profile.phone or "")}, instance=profile)
        if not form.is_valid(): return JsonResponse(_validation(form), status=400)
        return JsonResponse({"ok": True, "settings": _profile_payload(form.save())})


class StorefrontAccountPreferencesView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return JsonResponse({"ok": True, "preferences": _preferences(profile)})
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        form = NotificationPreferencesForm(data={name: coerce_bool(payload.get(name), getattr(profile, name)) for name in ("notify_email_orders", "notify_email_marketing", "notify_telegram_orders", "notify_telegram_marketing")}, instance=profile)
        if not form.is_valid(): return JsonResponse(_validation(form), status=400)
        return JsonResponse({"ok": True, "preferences": _preferences(form.save())})


class StorefrontAccountAddressesView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        rows = DeliveryAddress.objects.select_related("legal_entity").filter(legal_entity__members=request.user).order_by("-is_default", "label")
        return JsonResponse({"ok": True, "addresses": [_address(row) for row in rows]})
    def post(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        payload, error = request_payload(request)
        if error: return json_error(request, error, 400)
        form = AddressForm(data=payload, user=request.user)
        if not form.is_valid(): return JsonResponse(_validation(form), status=400)
        return JsonResponse({"ok": True, "address": _address(form.save())})


class StorefrontAccountAddressSetDefaultView(View):
    def post(self, request, address_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        row = DeliveryAddress.objects.select_related("legal_entity").filter(id=address_id, legal_entity__members=request.user).first()
        if not row: return json_error(request, "address_not_found", 404)
        row.is_default = True; row.save(update_fields=["is_default", "updated_at"])
        return JsonResponse({"ok": True, "address": _address(row)})


class StorefrontAccountAddressDeleteView(View):
    def post(self, request, address_id):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        row = DeliveryAddress.objects.filter(id=address_id, legal_entity__members=request.user).first()
        if not row: return json_error(request, "address_not_found", 404)
        row.delete(); return JsonResponse({"ok": True})


class StorefrontAccountLegalEntitiesView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        memberships = list(LegalEntityMembership.objects.select_related("legal_entity", "role").filter(user=request.user).order_by("legal_entity__name"))
        workspaces = _company_workspace_rows(request.user, memberships)
        requests = LegalEntityCreationRequest.objects.select_related("status").filter(applicant=request.user).order_by("-id")[:30]
        return JsonResponse({"ok": True, "memberships": [{"id": m.id, "legal_entity": {"id": m.legal_entity_id, "name": m.legal_entity.name, "inn": m.legal_entity.inn, "bik": m.legal_entity.bik, "checking_account": m.legal_entity.checking_account, "bank_name": m.legal_entity.bank_name or ""}, "role": {"code": getattr(m.role, "code", "") if m.role_id else "", "name": getattr(m.role, "name", "") if m.role_id else ""}} for m in memberships], "company_workspaces": [{"company_id": row["company"].id, "display_name": row["company"].display_name or row["company"].legal_entity.name, "legal_entity_id": row["legal_membership"].legal_entity_id, "membership_role": row["membership"].role if row["membership"] else "", "approval_policy": {"enabled": bool(row["policy"] and row["policy"].is_enabled), "auto_approve_below": money(row["policy"].auto_approve_below if row["policy"] else Decimal("0")), "required_approvals_count": int(row["policy"].required_approvals_count) if row["policy"] else 1, "require_comment": bool(row["policy"] and row["policy"].require_comment)}} for row in workspaces], "creation_requests": [{"id": r.id, "name": r.name, "inn": r.inn, "bik": r.bik, "checking_account": r.checking_account, "bank_name": r.bank_name or "", "status": {"code": getattr(r.status, "code", "") if r.status_id else "", "name": getattr(r.status, "name", "") if r.status_id else ""}, "created_at": r.created_at.isoformat()} for r in requests]})


class StorefrontAccountNotificationsView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        rows = _notification_feed(request.user, limit=120)
        return JsonResponse({"ok": True, "notifications": [{"at": row["at"].isoformat(), "title": row["title"], "subtitle": row["subtitle"], "href": row["href"]} for row in rows]})


class StorefrontAccountBootstrapView(View):
    def get(self, request):
        if not request.user.is_authenticated: return json_error(request, "authentication_required", 401)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        entity_ids = list(LegalEntityMembership.objects.filter(user=request.user).values_list("legal_entity_id", flat=True))
        recent = Order.objects.filter(placed_by=request.user).select_related("legal_entity").order_by("-created_at", "-id")[:8]
        unpaid = Order.objects.filter(placed_by=request.user, payment_method__in=[Order.PaymentMethod.INVOICE, Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD], status__in=[Order.Status.NEW, Order.Status.CONFIRMED, Order.Status.CHANGED]).select_related("legal_entity").order_by("-created_at", "-id")[:8]
        response = JsonResponse({"ok": True, "user": _user_payload(request.user), "profile": {"id": profile.id, "photo_url": profile.photo.url if profile.photo else "", "role": profile.role}, "metrics": {"orders_count": Order.objects.filter(placed_by=request.user).count(), "favorites_count": FavoriteProduct.objects.filter(user=request.user).count(), "saved_searches_count": SavedSearch.objects.filter(user=request.user).count(), "entities_count": len(entity_ids), "addresses_count": DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).count()}, "queues": {"recent_orders": [_order_short(o) for o in recent], "unpaid_orders": [_order_short(o) for o in unpaid]}, "links": {"orders": "/account/orders/", "addresses": "/account/addresses/", "legal": "/account/legal/", "notifications": "/account/notifications/", "preferences": "/account/preferences/"}})
        response["Cache-Control"] = "no-store"; response["Vary"] = "Cookie"; return response
