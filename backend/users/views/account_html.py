"""Buyer and company-account cabinet HTML views."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from core.logging_utils import log_calls

from ..forms import (
    AddressForm,
    ApprovalPolicyForm,
    CompanyContactForm,
    CompanyMemberInviteForm,
    CompanyMemberUpdateForm,
    CompanySettingsForm,
    LegalEntityRequestForm,
    NotificationPreferencesForm,
    OrderClaimForm,
    OrderClaimUpdateForm,
    OrderSupportTicketForm,
    ProfileForm,
)
from ..models import UserProfile
from shopfront.models import FavoriteProduct, SavedSearch
from shopfront.recommendation.service import order_reorder_candidates, reorder_recommendations
from .helpers import (
    _approval_approved_count,
    _approval_required_count,
    _approver_company_ids,
    _company_workspace_rows,
    _is_marketplace_admin,
    _managed_company_queryset,
    _notification_feed,
    _visible_orders_queryset,
    _is_seller,
    log,
    ensure_company_workspace,
    approver_memberships_for_company,
    ensure_approval_policy,
)


@log_calls()
def account_home(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
    preferences_form = NotificationPreferencesForm(request.POST or None, instance=profile, prefix="prefs")
    action = (request.POST.get("action") or "").strip()
    if request.method == "POST" and action == "save_preferences" and preferences_form.is_valid():
        preferences_form.save()
        messages.success(request, "Настройки уведомлений обновлены")
        return redirect("account_home")
    if request.method == "POST" and action != "save_preferences" and form.is_valid():
        form.save()
        messages.success(request, "Профиль обновлён")
        return redirect("account_home")
    from commerce.models import CompanyMembership, DeliveryAddress, LegalEntityMembership
    from orders.models import Order, OrderClaim, OrderSupportTicket
    from shopfront.models import BrandSubscription, CategorySubscription, SavedList

    entity_ids = list(LegalEntityMembership.objects.filter(user=request.user).values_list("legal_entity_id", flat=True))
    metrics = {
        "orders_count": Order.objects.filter(placed_by=request.user).count(),
        "saved_lists_count": SavedList.objects.filter(user=request.user).count(),
        "favorites_count": FavoriteProduct.objects.filter(user=request.user).count(),
        "saved_searches_count": SavedSearch.objects.filter(user=request.user).count(),
        "entities_count": len(entity_ids),
        "addresses_count": DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).count(),
        "subscriptions_count": BrandSubscription.objects.filter(user=request.user).count() + CategorySubscription.objects.filter(user=request.user).count(),
        "company_workspaces_count": CompanyMembership.objects.filter(user=request.user).count(),
        "orders_pending_approval_count": Order.objects.filter(legal_entity__members=request.user, approval_status=Order.ApprovalStatus.PENDING).count(),
    }
    if _is_seller(request):
        return redirect("account_seller_home")
    recent_orders = Order.objects.filter(placed_by=request.user).select_related("legal_entity").order_by("-created_at", "-id")[:6]
    unpaid_orders = Order.objects.filter(
        placed_by=request.user,
        payment_method__in=[Order.PaymentMethod.INVOICE, Order.PaymentMethod.MIR_CARD, Order.PaymentMethod.ONLINE_CARD],
        status__in=[Order.Status.NEW, Order.Status.CONFIRMED, Order.Status.CHANGED],
    ).order_by("-created_at", "-id")[:6]
    invoice_orders = Order.objects.filter(
        placed_by=request.user,
        payment_method=Order.PaymentMethod.INVOICE,
    ).order_by("-created_at", "-id")[:6]
    open_claims = OrderClaim.objects.filter(
        order__placed_by=request.user,
        status__in=[OrderClaim.Status.OPEN, OrderClaim.Status.IN_REVIEW],
    ).select_related("order").order_by("-updated_at", "-id")[:6]
    support_tickets = OrderSupportTicket.objects.filter(
        order__placed_by=request.user,
        status__in=[OrderSupportTicket.Status.OPEN, OrderSupportTicket.Status.IN_PROGRESS],
    ).select_related("order").order_by("-updated_at", "-id")[:6]
    company_memberships = CompanyMembership.objects.select_related("company", "company__legal_entity").filter(user=request.user).order_by("company__display_name", "company__legal_entity__name")
    return render(
        request,
        "account/home.html",
        {
            "form": form,
            "preferences_form": preferences_form,
            "notifications": _notification_feed(request.user, limit=8),
            "profile": profile,
            "metrics": metrics,
            "account_reorder_products": reorder_recommendations(request.user, limit=8),
            "account_replenishment_products": reorder_recommendations(request.user, limit=8),
            "recent_orders": recent_orders,
            "unpaid_orders": unpaid_orders,
            "invoice_orders": invoice_orders,
            "open_claims": open_claims,
            "support_tickets": support_tickets,
            "company_memberships": company_memberships,
            "account_section": "home",
        },
    )


@log_calls()
def account_addresses(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/addresses/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from commerce.models import DeliveryAddress, LegalEntityMembership

    entity_ids = list(LegalEntityMembership.objects.filter(user=request.user).values_list("legal_entity_id", flat=True))
    addresses = DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).order_by("-is_default", "label")
    form = AddressForm(request.POST or None, user=request.user)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Адрес добавлен")
            if request.headers.get("HX-Request"):
                updated = DeliveryAddress.objects.filter(legal_entity_id__in=entity_ids).order_by("-is_default", "label")
                resp = render(request, "account/partials/addresses_list.html", {"addresses": updated})
                resp["HX-Trigger"] = '{"showToast": {"message": "Адрес добавлен", "variant": "success"}}'
                return resp
            return redirect("account_addresses")
        if request.headers.get("HX-Request"):
            resp = render(request, "account/partials/form_errors.html", {"form": form})
            resp["HX-Retarget"] = "#address-form-errors"
            resp["HX-Reswap"] = "innerHTML"
            resp["HX-Trigger"] = '{"showToast": {"message": "Исправьте ошибки формы", "variant": "danger"}}'
            return resp
    if request.headers.get("HX-Request") and request.GET.get("fragment") == "list":
        return render(request, "account/partials/addresses_list.html", {"addresses": addresses})
    return render(
        request,
        "account/addresses.html",
        {
            "addresses": addresses,
            "form": form,
            "gmaps_key": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
            "profile": profile,
            "account_section": "addresses",
        },
    )


@log_calls()
def account_legal_entities(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/legal/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from commerce.models import LegalEntityCreationRequest, LegalEntityMembership

    my_memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=request.user)
    company_workspaces = _company_workspace_rows(request.user, my_memberships)
    form = LegalEntityRequestForm(request.POST or None)
    requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            LegalEntityCreationRequest.objects.create(
                applicant=request.user,
                name=data["name"],
                inn=data["inn"],
                bik=data.get("bik") or "",
                checking_account=data.get("checking_account") or "",
                bank_name=data.get("bank_name") or "",
            )
            messages.success(request, "Заявка отправлена на рассмотрение")
            if request.headers.get("HX-Request"):
                requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
                return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})
            return redirect("account_legal")
        messages.error(request, "Исправьте ошибки в форме")
    if request.headers.get("HX-Request"):
        frag = request.GET.get("fragment")
        if frag == "requests":
            return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})
        if frag == "memberships":
            my_memberships = LegalEntityMembership.objects.select_related("legal_entity").filter(user=request.user)
            return render(request, "account/partials/memberships_list.html", {"memberships": my_memberships})
    return render(
        request,
        "account/legal_entities.html",
        {
            "memberships": my_memberships,
            "company_workspaces": company_workspaces,
            "form": form,
            "requests": requests_qs,
            "profile": profile,
            "account_section": "legal",
        },
    )


@require_http_methods(["POST"])
@log_calls()
def cancel_legal_request(request, pk: int):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/legal/")
    from commerce.models import LegalEntityCreationRequest, RequestStatus

    obj = LegalEntityCreationRequest.objects.select_related("status").filter(id=pk, applicant=request.user).first()
    if obj and getattr(obj.status, "code", None) == "pending":
        obj.status = RequestStatus.objects.get(code="rejected")
        obj.save(update_fields=["status"])
        messages.success(request, "Заявка отменена")
    requests_qs = LegalEntityCreationRequest.objects.filter(applicant=request.user).order_by("-id")
    return render(request, "account/partials/legal_requests.html", {"requests": requests_qs})


@log_calls()
def account_orders(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/orders/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    orders = _visible_orders_queryset(request.user).order_by("-id")[:100]
    return render(
        request,
        "account/orders.html",
        {
            "orders": orders,
            "profile": profile,
            "order_reorder_products": reorder_recommendations(request.user, limit=8),
            "account_section": "orders",
        },
    )


@log_calls()
def account_order_detail(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    order = (
        _visible_orders_queryset(request.user)
        .select_related("legal_entity", "delivery_address")
        .prefetch_related(
            "items__product__images",
            "items__seller_offer",
            "seller_splits",
            "seller_orders",
            "seller_orders__items",
            "seller_orders__items__product",
            "seller_orders__items__seller_offer",
            "seller_orders__shipments",
            "seller_orders__shipments__items",
            "approval_logs",
            "approval_logs__actor",
            "claims",
            "claims__created_by",
            "claims__responded_by",
            "support_tickets",
            "support_tickets__created_by",
        )
        .filter(id=order_id)
        .first()
    )
    if not order:
        raise Http404("Order not found")
    fake_payment = getattr(order, "fake_payment", None)
    company = ensure_company_workspace(order.legal_entity) if order.legal_entity_id else None
    approval_policy = ensure_approval_policy(company) if company else None
    can_approve = bool(company and request.user.is_authenticated and approver_memberships_for_company(company).filter(user=request.user).exists())
    return render(
        request,
        "account/order_detail.html",
        {
            "order": order,
            "fake_payment": fake_payment,
            "demo_payments_enabled": bool(getattr(settings, "ENABLE_DEMO_PAYMENTS", settings.DEBUG)),
            "profile": profile,
            "account_section": "orders",
            "can_approve_order": can_approve,
            "approval_policy": approval_policy,
            "approval_required_count": _approval_required_count(order),
            "approval_approved_count": _approval_approved_count(order),
            "support_form": OrderSupportTicketForm(),
            "claim_update_form": OrderClaimUpdateForm(),
            "order_repeat_products": order_reorder_candidates(order, user=request.user, limit=6),
        },
    )


@require_POST
@log_calls()
def account_order_approval_action(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    from orders.models import OrderApprovalLog

    order = (
        _visible_orders_queryset(request.user)
        .select_related("legal_entity", "delivery_address")
        .prefetch_related("items__product__images", "seller_splits", "seller_orders", "seller_orders__shipments")
        .filter(id=order_id)
        .first()
    )
    if not order:
        raise Http404("Order not found")
    company = ensure_company_workspace(order.legal_entity) if order.legal_entity_id else None
    if not company or not approver_memberships_for_company(company).filter(user=request.user).exists():
        raise Http404("Approval not available")
    policy = ensure_approval_policy(company)
    action = (request.POST.get("action") or "").strip()
    comment = (request.POST.get("comment") or "").strip()
    if policy.require_comment and not comment:
        messages.error(request, "По текущей политике комментарий обязателен")
        return redirect("account_order_detail", order_id=order.id)
    if action == "approve":
        if OrderApprovalLog.objects.filter(order=order, actor=request.user, decision=OrderApprovalLog.Decision.APPROVED).exists():
            messages.error(request, "Вы уже согласовали этот заказ")
            return redirect("account_order_detail", order_id=order.id)
        OrderApprovalLog.objects.create(order=order, actor=request.user, decision=OrderApprovalLog.Decision.APPROVED, comment=comment)
        approvals_count = _approval_approved_count(order)
        required_count = max(1, int(policy.required_approvals_count or 1))
        if approvals_count >= required_count:
            from django.utils import timezone

            order.approval_status = order.ApprovalStatus.APPROVED
            order.approved_by = request.user
            order.approved_at = timezone.now()
            order.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])
            messages.success(request, "Заказ согласован")
        else:
            messages.success(request, f"Шаг согласования сохранён: {approvals_count}/{required_count}")
    elif action == "reject":
        from django.utils import timezone

        order.approval_status = order.ApprovalStatus.REJECTED
        order.approved_by = request.user
        order.approved_at = timezone.now()
        if order.status not in {order.Status.CANCELED, order.Status.DELIVERED}:
            order.status = order.Status.CANCELED
        order.save(update_fields=["approval_status", "approved_by", "approved_at", "status", "updated_at"])
        OrderApprovalLog.objects.create(order=order, actor=request.user, decision=OrderApprovalLog.Decision.REJECTED, comment=comment)
        messages.warning(request, "Заказ отклонён")
    return redirect("account_order_detail", order_id=order.id)


@require_POST
@log_calls()
def account_order_cancel(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    from orders.models import SellerOrder

    order = _visible_orders_queryset(request.user).filter(id=order_id, placed_by=request.user).first()
    if not order:
        raise Http404("Order not found")
    if order.status in {order.Status.CANCELED, order.Status.DELIVERED}:
        messages.error(request, "Этот заказ уже нельзя отменить")
        return redirect("account_order_detail", order_id=order.id)
    order.cancel()
    order.approval_status = order.ApprovalStatus.REJECTED if order.approval_status == order.ApprovalStatus.PENDING else order.approval_status
    order.save(update_fields=["status", "approval_status", "updated_at"])
    SellerOrder.objects.filter(order=order).update(status=SellerOrder.Status.CANCELED)
    messages.success(request, "Заказ отменён")
    return redirect("account_order_detail", order_id=order.id)


@require_POST
@log_calls()
def account_order_reorder(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    from shopfront.cart_mutation_service import add_to_cart_session

    order = _visible_orders_queryset(request.user).prefetch_related("items").filter(id=order_id, placed_by=request.user).first()
    if not order:
        raise Http404("Order not found")
    added = 0
    for item in order.items.all():
        add_to_cart_session(request=request, product_id=item.product_id, qty=max(1, int(item.qty or 1)), logger=log)
        added += 1
    if added:
        messages.success(request, "Товары из заказа перенесены в корзину")
    else:
        messages.error(request, "В заказе нет доступных товаров для повтора")
    return redirect("/cart/")


@log_calls()
def account_order_invoice(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    from core.pdf import render_invoice_pdf

    order = _visible_orders_queryset(request.user).filter(id=order_id).first()
    if not order:
        raise Http404("Order not found")
    pdf_path, filename = render_invoice_pdf(order)
    return FileResponse(open(pdf_path, "rb"), as_attachment=True, filename=filename)


@log_calls()
def account_order_tracking(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/tracking/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    order = _visible_orders_queryset(request.user).prefetch_related("seller_orders", "seller_orders__shipments", "seller_orders__shipments__items").filter(id=order_id).first()
    if not order:
        raise Http404("Order not found")
    return render(request, "account/order_tracking.html", {"order": order, "profile": profile, "account_section": "orders"})


@log_calls()
def account_notifications(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/notifications/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "account/notifications.html", {"profile": profile, "notifications": _notification_feed(request.user, limit=120), "account_section": "notifications"})


@log_calls()
def account_preferences(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/preferences/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    form = NotificationPreferencesForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Предпочтения уведомлений сохранены")
        return redirect("account_preferences")
    return render(request, "account/preferences.html", {"profile": profile, "form": form, "account_section": "preferences"})


@log_calls()
def account_marketplace_ops(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/marketplace/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_marketplace_admin(request.user):
        messages.error(request, "Раздел доступен только staff/admin")
        return redirect("account_home")
    from catalog.models import Product
    from commerce.models import SellerStore

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "update_store":
            store = SellerStore.objects.filter(id=request.POST.get("store_id")).first()
            status = (request.POST.get("moderation_status") or "").strip()
            if store and status in {choice[0] for choice in SellerStore.ModerationStatus.choices}:
                store.moderation_status = status
                store.moderation_note = (request.POST.get("moderation_note") or "").strip()
                store.commission_rate = request.POST.get("commission_rate") or store.commission_rate
                store.save(update_fields=["moderation_status", "moderation_note", "commission_rate", "updated_at"])
                messages.success(request, "Store updated")
                return redirect("account_marketplace_ops")
        if action == "update_product":
            product = Product.objects.filter(id=request.POST.get("product_id")).first()
            status = (request.POST.get("publication_status") or "").strip()
            if product and status in {choice[0] for choice in Product.PublicationStatus.choices}:
                product.publication_status = status
                product.save(update_fields=["publication_status", "updated_at"])
                messages.success(request, "Product publication status updated")
                return redirect("account_marketplace_ops")

    stores = SellerStore.objects.select_related("owner", "legal_entity").order_by("moderation_status", "-updated_at")[:100]
    products = Product.objects.select_related("seller", "brand", "category").order_by("publication_status", "-updated_at")[:100]
    return render(request, "account/marketplace_ops.html", {"profile": profile, "stores": stores, "products": products, "account_section": "marketplace_ops"})


@require_POST
@log_calls()
def account_order_claim_create(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    order = _visible_orders_queryset(request.user).filter(id=order_id).first()
    if not order:
        raise Http404("Order not found")
    form = OrderClaimForm(request.POST or None)
    if form.is_valid():
        claim = form.save(commit=False)
        claim.order = order
        claim.created_by = request.user
        claim.save()
        messages.success(request, "Диспут по заказу создан")
    else:
        messages.error(request, "Не удалось создать обращение")
    return redirect("account_order_detail", order_id=order.id)


@require_POST
@log_calls()
def account_order_support_create(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    order = _visible_orders_queryset(request.user).filter(id=order_id).first()
    if not order:
        raise Http404("Order not found")
    form = OrderSupportTicketForm(request.POST or None)
    if form.is_valid():
        ticket = form.save(commit=False)
        ticket.order = order
        ticket.created_by = request.user
        ticket.save()
        messages.success(request, "Обращение в поддержку создано")
    else:
        messages.error(request, "Не удалось создать обращение в поддержку")
    return redirect("account_order_detail", order_id=order.id)


@log_calls()
def account_order_retry_payment(request, order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/orders/{order_id}/")
    order = _visible_orders_queryset(request.user).filter(id=order_id, placed_by=request.user).first()
    if not order:
        raise Http404("Order not found")
    if not bool(getattr(settings, "ENABLE_DEMO_PAYMENTS", settings.DEBUG)):
        messages.error(request, "Sandbox-платежи отключены в этом окружении")
        return redirect("account_order_detail", order_id=order.id)
    if order.payment_method not in {order.PaymentMethod.MIR_CARD, order.PaymentMethod.ONLINE_CARD} or not getattr(order, "fake_payment", None):
        messages.error(request, "Повторная оплата недоступна для этого заказа")
        return redirect("account_order_detail", order_id=order.id)
    if order.payment_method == order.PaymentMethod.ONLINE_CARD:
        return redirect("online_payment_page", order_id=order.id)
    return redirect("fake_payment_page", order_id=order.id)


@log_calls()
def account_approvals(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/approvals/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from orders.models import OrderApprovalLog

    pending_orders = _visible_orders_queryset(request.user).filter(approval_status="pending", legal_entity__company__id__in=_approver_company_ids(request.user)).order_by("-created_at", "-id")[:100]
    recent_logs = OrderApprovalLog.objects.select_related("order", "actor", "order__legal_entity").filter(order__legal_entity__company__id__in=_approver_company_ids(request.user)).order_by("-created_at", "-id")[:50]
    progress_map = {order.id: {"required": _approval_required_count(order), "approved": _approval_approved_count(order)} for order in pending_orders}
    return render(request, "account/approvals.html", {"orders": pending_orders, "recent_logs": recent_logs, "progress_map": progress_map, "profile": profile, "account_section": "approvals"})


@log_calls()
def account_company_members(request, company_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/legal/company/{company_id}/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from commerce.models import CompanyContact, CompanyMembership, LegalEntityMembership, MembershipRole

    company = _managed_company_queryset(request.user).select_related("legal_entity").filter(id=company_id).first()
    if not company:
        raise Http404("Company not found")
    policy = ensure_approval_policy(company)
    invite_form = CompanyMemberInviteForm(request.POST or None, prefix="invite")
    settings_form = CompanySettingsForm(request.POST or None, instance=company, prefix="company")
    contact_form = CompanyContactForm(request.POST or None, prefix="contact")
    policy_form = ApprovalPolicyForm(
        request.POST or None,
        prefix="policy",
        initial={
            "is_enabled": policy.is_enabled,
            "auto_approve_below": policy.auto_approve_below,
            "require_approver_role": policy.require_approver_role,
            "require_comment": policy.require_comment,
            "required_approvals_count": policy.required_approvals_count,
            "max_pending_hours": policy.max_pending_hours,
        },
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "save_company_settings" and settings_form.is_valid():
            settings_form.save()
            messages.success(request, "Настройки компании обновлены")
            return redirect("account_company_members", company_id=company.id)
        if action == "add_contact" and contact_form.is_valid():
            contact = contact_form.save(commit=False)
            contact.company = company
            contact.save()
            messages.success(request, "Контакт компании добавлен")
            return redirect("account_company_members", company_id=company.id)
        if action == "update_policy" and policy_form.is_valid():
            policy.is_enabled = bool(policy_form.cleaned_data.get("is_enabled"))
            policy.auto_approve_below = policy_form.cleaned_data.get("auto_approve_below") or 0
            policy.require_approver_role = bool(policy_form.cleaned_data.get("require_approver_role"))
            policy.require_comment = bool(policy_form.cleaned_data.get("require_comment"))
            policy.required_approvals_count = policy_form.cleaned_data.get("required_approvals_count") or 1
            policy.max_pending_hours = policy_form.cleaned_data.get("max_pending_hours") or 24
            policy.save(update_fields=["is_enabled", "auto_approve_below", "require_approver_role", "require_comment", "required_approvals_count", "max_pending_hours", "updated_at"])
            messages.success(request, "Approval policy обновлена")
            return redirect("account_company_members", company_id=company.id)
        if action == "invite_member" and invite_form.is_valid():
            identifier = invite_form.cleaned_data["identifier"]
            User = get_user_model()
            member_user = User.objects.filter(username=identifier).first() or User.objects.filter(email__iexact=identifier).first()
            if member_user is None:
                messages.error(request, "Пользователь не найден")
            else:
                membership, _ = CompanyMembership.objects.update_or_create(
                    user=member_user,
                    company=company,
                    defaults={
                        "role": invite_form.cleaned_data["role"],
                        "approval_limit": invite_form.cleaned_data.get("approval_limit") or 0,
                        "is_default_approver": bool(invite_form.cleaned_data.get("is_default_approver")),
                    },
                )
                manager_role, _ = MembershipRole.objects.get_or_create(code="manager", defaults={"name": "Менеджер"})
                LegalEntityMembership.objects.get_or_create(user=member_user, legal_entity=company.legal_entity, defaults={"role": manager_role})
                membership.refresh_from_db()
                membership.role = invite_form.cleaned_data["role"]
                membership.approval_limit = invite_form.cleaned_data.get("approval_limit") or 0
                membership.is_default_approver = bool(invite_form.cleaned_data.get("is_default_approver"))
                membership.save(update_fields=["role", "approval_limit", "is_default_approver", "updated_at"])
                messages.success(request, f"Участник {membership.user.username} добавлен в компанию")
                return redirect("account_company_members", company_id=company.id)
        elif action == "update_member":
            member_id = request.POST.get("member_id")
            membership = CompanyMembership.objects.filter(id=member_id, company=company).first()
            if membership is None:
                messages.error(request, "Участник компании не найден")
            else:
                update_form = CompanyMemberUpdateForm(request.POST, prefix=f"member-{membership.id}")
                if update_form.is_valid():
                    membership.role = update_form.cleaned_data["role"]
                    membership.approval_limit = update_form.cleaned_data.get("approval_limit") or 0
                    membership.is_default_approver = bool(update_form.cleaned_data.get("is_default_approver"))
                    membership.save(update_fields=["role", "approval_limit", "is_default_approver", "updated_at"])
                    messages.success(request, "Параметры участника обновлены")
                    return redirect("account_company_members", company_id=company.id)
        elif action == "remove_member":
            member_id = request.POST.get("member_id")
            membership = CompanyMembership.objects.filter(id=member_id, company=company).first()
            if membership is None:
                messages.error(request, "Участник компании не найден")
            elif membership.user_id == request.user.id:
                messages.error(request, "Нельзя удалить самого себя из компании")
            else:
                membership.delete()
                messages.success(request, "Участник удалён из company workspace")
                return redirect("account_company_members", company_id=company.id)
        elif action == "delete_contact":
            contact = CompanyContact.objects.filter(company=company, id=request.POST.get("contact_id")).first()
            if contact:
                contact.delete()
                messages.success(request, "Контакт удалён")
                return redirect("account_company_members", company_id=company.id)
    members = CompanyMembership.objects.filter(company=company).select_related("user").order_by("role", "user__username")
    member_forms = {
        membership.id: CompanyMemberUpdateForm(
            prefix=f"member-{membership.id}",
            initial={"role": membership.role, "approval_limit": membership.approval_limit, "is_default_approver": membership.is_default_approver},
        )
        for membership in members
    }
    return render(
        request,
        "account/company_members.html",
        {
            "profile": profile,
            "company": company,
            "policy": policy,
            "policy_form": policy_form,
            "settings_form": settings_form,
            "contact_form": contact_form,
            "contacts": company.contacts.all(),
            "members": members,
            "invite_form": invite_form,
            "member_forms": member_forms,
            "account_section": "legal",
        },
    )


@log_calls()
def account_comments(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/comments/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from catalog.models import ProductImage, ProductReviewComment

    comments = (
        ProductReviewComment.objects.select_related("review__product")
        .prefetch_related(
            Prefetch(
                "review__product__images",
                queryset=ProductImage.objects.only("id", "product_id", "url", "ordering").order_by("ordering", "id"),
                to_attr="prefetched_images",
            )
        )
        .filter(user=request.user)
        .order_by("-created_at", "-id")[:200]
    )
    return render(request, "account/comments.html", {"comments": comments, "profile": profile, "account_section": "comments"})
