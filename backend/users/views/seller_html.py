"""Seller-facing cabinet HTML views."""

from __future__ import annotations

import csv
from io import StringIO
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, Count, Prefetch, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.logging_utils import log_calls

from ..forms import (
    InventoryAdjustmentForm,
    OrderClaimUpdateForm,
    OrderSupportTicketUpdateForm,
    ProductDocumentForm,
    SellerInventoryForm,
    SellerOfferForm,
    SellerOrderItemCancelForm,
    SellerProductBulkActionForm,
    SellerProductCreateForm,
    SellerProductImportForm,
    SellerQuestionAnswerForm,
    SellerReviewReplyForm,
    SellerStoreForm,
    ShipmentCreateForm,
)
from ..models import UserProfile
from .helpers import (
    SELLER_PRODUCT_IMPORT_HEADERS,
    _can_manage_product,
    _import_seller_products_from_csv,
    _is_seller,
    _notification_feed,
    _save_linked_product_images,
    _save_product_document,
    _save_uploaded_product_images,
    _seller_order_allocation_maps,
    _sync_parent_order_status_from_seller_orders,
    _sync_seller_order_fulfillment_status,
    _visible_seller_orders_queryset,
)


@log_calls()
def account_seller_orders(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/orders/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import SellerOrder

    qs = _visible_seller_orders_queryset(request.user)
    status_filter = (request.GET.get("status") or "").strip()
    if status_filter in {choice[0] for choice in SellerOrder.Status.choices}:
        qs = qs.filter(status=status_filter)
    seller_orders = qs.order_by("-created_at", "-id")[:100]
    return render(
        request,
        "account/seller_orders.html",
        {
            "profile": profile,
            "seller_orders": seller_orders,
            "status_filter": status_filter,
            "account_section": "seller_orders",
        },
    )


@log_calls()
def account_seller_order_detail(request, seller_order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import OrderClaim, OrderSupportTicket

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    allocation_maps = _seller_order_allocation_maps(seller_order)
    claims = OrderClaim.objects.filter(order=seller_order.order).select_related("created_by", "responded_by").order_by("-updated_at", "-id")
    tickets = OrderSupportTicket.objects.filter(order=seller_order.order).select_related("created_by").order_by("-updated_at", "-id")
    return render(
        request,
        "account/seller_order_detail.html",
        {
            "profile": profile,
            "seller_order": seller_order,
            "claim_forms": {claim.id: OrderClaimUpdateForm(instance=claim) for claim in claims},
            "support_forms": {ticket.id: OrderSupportTicketUpdateForm(initial={"status": ticket.status, "resolution_comment": ticket.resolution_comment}) for ticket in tickets},
            "claims": claims,
            "support_tickets": tickets,
            "shipment_create_form": ShipmentCreateForm(),
            "allocation_maps": allocation_maps,
            "account_section": "seller_orders",
        },
    )


@require_POST
@log_calls()
def account_seller_claim_update(request, seller_order_id: int, claim_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import OrderClaim

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    claim = OrderClaim.objects.filter(id=claim_id, order=seller_order.order).first()
    if not claim:
        raise Http404("Claim not found")
    form = OrderClaimUpdateForm(request.POST or None, instance=claim)
    if form.is_valid():
        claim = form.save(commit=False)
        claim.responded_by = request.user
        claim.save()
        messages.success(request, "Диспут обновлён")
    else:
        messages.error(request, "Не удалось обновить диспут")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_support_ticket_update(request, seller_order_id: int, ticket_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import OrderSupportTicket

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    ticket = OrderSupportTicket.objects.filter(id=ticket_id, order=seller_order.order).first()
    if not ticket:
        raise Http404("Support ticket not found")
    form = OrderSupportTicketUpdateForm(request.POST or None)
    if form.is_valid():
        ticket.status = form.cleaned_data["status"]
        ticket.resolution_comment = form.cleaned_data.get("resolution_comment") or ""
        ticket.save(update_fields=["status", "resolution_comment", "updated_at"])
        messages.success(request, "Support ticket обновлён")
    else:
        messages.error(request, "Не удалось обновить support ticket")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_order_status_action(request, seller_order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import SellerOrder
    from orders.services import mark_seller_order_status

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    target_status = (request.POST.get("status") or "").strip()
    allowed_statuses = {
        SellerOrder.Status.ACCEPTED,
        SellerOrder.Status.PICKING,
        SellerOrder.Status.SHIPPED,
        SellerOrder.Status.DELIVERED,
        SellerOrder.Status.CANCELED,
    }
    if target_status not in allowed_statuses:
        messages.error(request, "Некорректный статус seller order")
        return redirect("account_seller_order_detail", seller_order_id=seller_order.id)
    if target_status in {SellerOrder.Status.ACCEPTED, SellerOrder.Status.SHIPPED, SellerOrder.Status.DELIVERED}:
        mark_seller_order_status(seller_order, target_status)
    else:
        seller_order.status = target_status
        seller_order.save(update_fields=["status", "updated_at"])
    seller_order.refresh_from_db()
    _sync_parent_order_status_from_seller_orders(seller_order.order)
    messages.success(request, "Статус seller order обновлён")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_shipment_update(request, seller_order_id: int, shipment_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import Shipment

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    shipment = seller_order.shipments.filter(id=shipment_id).first()
    if not shipment:
        raise Http404("Shipment not found")
    shipment.tracking_number = (request.POST.get("tracking_number") or "").strip()
    shipment.delivery_method = (request.POST.get("delivery_method") or "").strip()
    shipment.warehouse_name = (request.POST.get("warehouse_name") or "").strip()
    target_status = (request.POST.get("status") or "").strip()
    allowed_statuses = {choice[0] for choice in Shipment.Status.choices}
    if target_status in {Shipment.Status.READY, Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED} and not shipment.items.filter(qty__gt=0).exists():
        messages.error(request, "Сначала распределите хотя бы одну позицию в shipment")
        return redirect("account_seller_order_detail", seller_order_id=seller_order.id)
    if target_status in allowed_statuses:
        shipment.status = target_status
        now = timezone.now()
        if target_status == Shipment.Status.READY and shipment.packed_at is None:
            shipment.packed_at = now
        if target_status == Shipment.Status.IN_TRANSIT and shipment.shipped_at is None:
            shipment.shipped_at = now
        if target_status == Shipment.Status.DELIVERED and shipment.delivered_at is None:
            shipment.delivered_at = now
    shipment.save()
    fresh_seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order.id).first()
    _sync_seller_order_fulfillment_status(fresh_seller_order)
    _sync_parent_order_status_from_seller_orders(fresh_seller_order.order)
    messages.success(request, "Отгрузка обновлена")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_shipment_create(request, seller_order_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import Shipment

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    form = ShipmentCreateForm(request.POST)
    if form.is_valid():
        Shipment.objects.create(
            seller_order=seller_order,
            warehouse_name=form.cleaned_data.get("warehouse_name") or seller_order.seller_store_name or "Основной склад",
            delivery_method=form.cleaned_data.get("delivery_method") or "marketplace_split",
            status=Shipment.Status.DRAFT,
        )
        messages.success(request, "Новая частичная отгрузка создана")
    else:
        messages.error(request, "Не удалось создать shipment")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_shipment_items_update(request, seller_order_id: int, shipment_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import Shipment, ShipmentItem

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    shipment = seller_order.shipments.filter(id=shipment_id).first()
    if not shipment:
        raise Http404("Shipment not found")
    if shipment.status in {Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED}:
        messages.error(request, "Нельзя менять состав shipment после отправки")
        return redirect("account_seller_order_detail", seller_order_id=seller_order.id)

    allocation_maps = _seller_order_allocation_maps(seller_order)
    current_allocations = allocation_maps["shipment_allocations"].get(shipment.id, {})
    with transaction.atomic():
        for item in seller_order.items.all():
            raw_value = (request.POST.get(f"item_{item.id}_qty") or "0").strip()
            try:
                qty = max(0, int(raw_value or 0))
            except ValueError:
                qty = 0
            other_allocated = allocation_maps["item_allocated"].get(item.id, 0) - current_allocations.get(item.id, 0)
            allowed_qty = max(0, int(item.active_qty) - other_allocated)
            qty = min(qty, allowed_qty)
            shipment_item = shipment.items.filter(seller_order_item=item).first()
            if qty <= 0:
                if shipment_item:
                    shipment_item.delete()
                continue
            if shipment_item:
                shipment_item.qty = qty
                shipment_item.save(update_fields=["qty", "updated_at"])
            else:
                ShipmentItem.objects.create(shipment=shipment, seller_order_item=item, qty=qty)
    messages.success(request, "Состав shipment обновлён")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@require_POST
@log_calls()
def account_seller_order_item_cancel(request, seller_order_id: int, item_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/orders/{seller_order_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.services import recalc_order_totals_from_items, recalc_seller_order_totals, trim_shipment_allocations

    seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order_id).first()
    if not seller_order:
        raise Http404("Seller order not found")
    seller_order_item = seller_order.items.filter(id=item_id).select_related("order_item").first()
    if not seller_order_item:
        raise Http404("Seller order item not found")

    form = SellerOrderItemCancelForm(request.POST)
    if not form.is_valid() or form.cleaned_data["seller_order_item_id"] != seller_order_item.id:
        messages.error(request, "Некорректные данные для отмены позиции")
        return redirect("account_seller_order_detail", seller_order_id=seller_order.id)

    allocation_maps = _seller_order_allocation_maps(seller_order)
    locked_qty = allocation_maps["item_locked"].get(seller_order_item.id, 0)
    cancelable_qty = max(0, int(seller_order_item.active_qty) - locked_qty)
    cancel_qty = min(int(form.cleaned_data["cancel_qty"]), cancelable_qty)
    if cancel_qty <= 0:
        messages.error(request, "Нельзя отменить уже отправленное количество")
        return redirect("account_seller_order_detail", seller_order_id=seller_order.id)

    with transaction.atomic():
        seller_order_item.canceled_qty += cancel_qty
        seller_order_item.save(update_fields=["canceled_qty", "updated_at"])
        seller_order_item.order_item.canceled_qty += cancel_qty
        seller_order_item.order_item.save(update_fields=["canceled_qty", "updated_at"])
        trim_shipment_allocations(seller_order_item)
        fresh_seller_order = seller_order.__class__.objects.get(pk=seller_order.pk)
        recalc_seller_order_totals(fresh_seller_order)
        recalc_order_totals_from_items(fresh_seller_order.order)

    fresh_seller_order = _visible_seller_orders_queryset(request.user).filter(id=seller_order.id).first()
    _sync_seller_order_fulfillment_status(fresh_seller_order)
    _sync_parent_order_status_from_seller_orders(fresh_seller_order.order)
    messages.success(request, f"Отменено {cancel_qty} шт. по позиции")
    return redirect("account_seller_order_detail", seller_order_id=seller_order.id)


@log_calls()
def account_seller_home(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")

    from catalog.models import Product, ProductQuestion, ProductReview, SellerInventory, SellerOffer
    from commerce.models import LegalEntityMembership
    from orders.models import Order, SellerOrder, Shipment

    store = getattr(request.user, "seller_store", None)
    form = SellerStoreForm(request.POST or None, request.FILES or None, instance=store, user=request.user)
    if request.method == "POST" and form.is_valid():
        store_obj = form.save(commit=False)
        store_obj.owner = request.user
        store_obj.save()
        messages.success(request, "Магазин продавца сохранён")
        return redirect("account_seller_home")

    memberships_qs = LegalEntityMembership.objects.filter(user=request.user)
    seller_orders_qs = SellerOrder.objects.filter(seller=request.user)
    overdue_cutoff = timezone.now() - timedelta(hours=getattr(store, "sla_target_hours", 24) or 24)
    stale_stock_cutoff = timezone.now() - timedelta(days=30)
    products_qs = Product.objects.filter(seller=request.user)
    active_offer_product_ids = set(
        SellerOffer.objects.filter(seller=request.user, status=SellerOffer.Status.ACTIVE).values_list("product_id", flat=True)
    )
    products_without_offer_count = products_qs.exclude(id__in=active_offer_product_ids).count()
    products_without_images_count = products_qs.filter(images__isnull=True).distinct().count()
    products_without_documents_count = products_qs.filter(documents__isnull=True).distinct().count()
    products_stale_stock_count = products_qs.filter(updated_at__lt=stale_stock_cutoff, stock_qty__gt=0).count()
    unanswered_questions = ProductQuestion.objects.filter(product__seller=request.user, answered_at__isnull=True)
    reviews_without_reply = ProductReview.objects.filter(product__seller=request.user).exclude(comments__user=request.user).distinct()
    overdue_shipments = Shipment.objects.filter(
        seller_order__seller=request.user,
        status__in=[Shipment.Status.DRAFT, Shipment.Status.READY, Shipment.Status.ISSUE],
        created_at__lt=overdue_cutoff,
    )
    invoice_mismatch_orders = seller_orders_qs.filter(
        order__payment_method=Order.PaymentMethod.INVOICE,
        order__status__in=[Order.Status.NEW, Order.Status.CONFIRMED, Order.Status.CHANGED],
    ).distinct()
    seller_metrics = {
        "products_count": Product.objects.filter(seller=request.user).count(),
        "in_stock_count": Product.objects.filter(seller=request.user, stock_qty__gt=0).count(),
        "entities_count": memberships_qs.count(),
        "seller_orders_count": seller_orders_qs.count(),
        "seller_orders_new_count": seller_orders_qs.filter(status=SellerOrder.Status.NEW).count(),
        "low_inventory_count": SellerInventory.objects.filter(offer__seller=request.user, stock_qty__lte=5).count(),
        "gmv": seller_orders_qs.exclude(status=SellerOrder.Status.CANCELED).aggregate(total=Sum("total"))["total"] or 0,
        "claims_open_count": seller_orders_qs.filter(order__claims__status__in=["open", "in_review"]).distinct().count(),
        "overdue_shipments_count": overdue_shipments.count(),
        "unanswered_questions_count": unanswered_questions.count(),
        "reviews_without_reply_count": reviews_without_reply.count(),
        "invoice_mismatch_count": invoice_mismatch_orders.count(),
        "products_without_images_count": products_without_images_count,
        "products_without_documents_count": products_without_documents_count,
        "products_without_offer_count": products_without_offer_count,
        "products_stale_stock_count": products_stale_stock_count,
    }
    latest_products = Product.objects.filter(seller=request.user).select_related("brand", "category").order_by("-updated_at", "-id")[:8]
    latest_seller_orders = (
        SellerOrder.objects.select_related("order").prefetch_related("items").annotate(item_count=Count("items", distinct=True)).filter(seller=request.user).order_by("-created_at", "-id")[:8]
    )
    latest_unanswered_questions = unanswered_questions.select_related("product", "user").order_by("-created_at", "-id")[:4]
    latest_reviews_without_reply = reviews_without_reply.select_related("product", "user").order_by("-created_at", "-id")[:4]
    quality_queue = [
        {
            "label": "Без фото",
            "count": products_without_images_count,
            "href": "/account/seller/products/add/",
            "meta": "Карточки без доверительного медиа-слоя",
        },
        {
            "label": "Без документов",
            "count": products_without_documents_count,
            "href": "/account/seller/products/add/",
            "meta": "Сертификаты и спецификации не загружены",
        },
        {
            "label": "Без активного оффера",
            "count": products_without_offer_count,
            "href": "/account/seller/offers/",
            "meta": "Карточки не участвуют в выдаче как полноценные предложения",
        },
        {
            "label": "Остатки устарели",
            "count": products_stale_stock_count,
            "href": "/account/seller/warehouses/",
            "meta": "Пора обновить stock и ETA",
        },
    ]
    return render(
        request,
        "account/seller_home.html",
        {
            "profile": profile,
            "store": store,
            "store_form": form,
            "seller_metrics": seller_metrics,
            "latest_products": latest_products,
            "latest_seller_orders": latest_seller_orders,
            "latest_unanswered_questions": latest_unanswered_questions,
            "latest_reviews_without_reply": latest_reviews_without_reply,
            "quality_queue": quality_queue,
            "notifications": _notification_feed(request.user, limit=8),
            "account_section": "seller_home",
        },
    )


@log_calls()
def account_seller_product_add(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/products/add/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")

    store = getattr(request.user, "seller_store", None)
    if store is None:
        messages.error(request, "Сначала настройте магазин продавца")
        return redirect("account_seller_home")

    form = SellerProductCreateForm(request.POST or None, request.FILES or None, user=request.user)
    import_form = SellerProductImportForm(request.POST or None, request.FILES or None)
    bulk_form = SellerProductBulkActionForm(request.POST or None)
    document_form = ProductDocumentForm(request.POST or None, prefix="doc")
    import_result = None
    if request.method == "POST":
        workflow = (request.POST.get("workflow") or request.POST.get("action") or "create_product").strip()
        if workflow == "create_product" and form.is_valid():
            product = form.save()
            _save_linked_product_images(product, form.cleaned_data.get("image_urls"))
            _save_uploaded_product_images(product, request.FILES.getlist("image_files"))
            messages.success(request, f"Товар '{product.name}' добавлен")
            return redirect("account_seller_products_add")
        if workflow == "import_catalog" and import_form.is_valid():
            import_result = _import_seller_products_from_csv(user=request.user, uploaded_file=import_form.cleaned_data["csv_file"])
            if import_result["errors"]:
                messages.error(request, "Импорт не выполнен полностью. Проверьте ошибки валидации ниже.")
            else:
                messages.success(request, f"Импорт завершён: создано {import_result['created']}, обновлено {import_result['updated']}")
                return redirect("account_seller_products_add")
        if workflow == "bulk_update" and bulk_form.is_valid():
            selected_ids = [int(product_id) for product_id in request.POST.getlist("product_ids") if str(product_id).isdigit()]
            from catalog.models import Product

            queryset = Product.objects.filter(seller=request.user, id__in=selected_ids)
            if not selected_ids or not queryset.exists():
                messages.error(request, "Для массовой операции выберите хотя бы один товар")
            else:
                bulk_action = bulk_form.cleaned_data["action"]
                updated = 0
                if bulk_action == "set_promo_on":
                    updated = queryset.update(is_promo=True)
                elif bulk_action == "set_promo_off":
                    updated = queryset.update(is_promo=False)
                elif bulk_action == "set_new_on":
                    updated = queryset.update(is_new=True)
                elif bulk_action == "set_new_off":
                    updated = queryset.update(is_new=False)
                elif bulk_action == "add_stock":
                    for product in queryset:
                        product.stock_qty = max(0, int(product.stock_qty or 0) + int(bulk_form.cleaned_data["stock_delta"] or 0))
                        product.save(update_fields=["stock_qty", "updated_at"])
                        updated += 1
                elif bulk_action == "set_lead_time":
                    updated = queryset.update(lead_time_days=bulk_form.cleaned_data["lead_time_days"])
                elif bulk_action == "set_draft":
                    updated = queryset.update(publication_status=Product.PublicationStatus.DRAFT)
                elif bulk_action == "set_published":
                    updated = queryset.update(publication_status=Product.PublicationStatus.PUBLISHED)
                elif bulk_action == "set_archived":
                    updated = queryset.update(publication_status=Product.PublicationStatus.ARCHIVED)
                messages.success(request, f"Массовая операция выполнена для {updated} товаров")
                return redirect("account_seller_products_add")

    from catalog.models import Product

    my_products = Product.objects.filter(seller=request.user).select_related("brand", "category").prefetch_related("images", "documents").order_by("-updated_at", "-id")[:50]
    return render(
        request,
        "account/seller_product_add.html",
        {
            "profile": profile,
            "store": store,
            "form": form,
            "import_form": import_form,
            "bulk_form": bulk_form,
            "document_form": document_form,
            "import_result": import_result,
            "my_products": my_products,
            "page_mode": "create",
            "account_section": "seller_products",
        },
    )


@log_calls()
def account_seller_product_edit(request, product_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/products/{product_id}/edit/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    from catalog.models import Product, ProductDocument, ProductImage

    product = Product.objects.select_related("brand", "series", "category", "seller").prefetch_related("images", "documents").filter(id=product_id).first()
    if product is None or not _can_manage_product(request.user, product):
        raise Http404("Product not found")

    form = SellerProductCreateForm(request.POST or None, request.FILES or None, instance=product, user=product.seller or request.user)
    document_form = ProductDocumentForm(request.POST or None, prefix="doc")
    if request.method == "POST":
        workflow = (request.POST.get("workflow") or "create_product").strip()
        if workflow == "create_product" and form.is_valid():
            product = form.save()
            remove_image_ids = [int(image_id) for image_id in request.POST.getlist("remove_image_ids") if str(image_id).isdigit()]
            if remove_image_ids:
                ProductImage.objects.filter(product=product, id__in=remove_image_ids).delete()
            _save_linked_product_images(product, form.cleaned_data.get("image_urls"))
            _save_uploaded_product_images(product, request.FILES.getlist("image_files"))
            ordering_map = {
                image.id: int(request.POST.get(f"image_order_{image.id}") or image.ordering or 0)
                for image in product.images.all()
                if str(request.POST.get(f"image_order_{image.id}") or "").strip()
            }
            primary_image_id = request.POST.get("primary_image_id")
            from .helpers import _reorder_product_images

            _reorder_product_images(product, int(primary_image_id) if str(primary_image_id).isdigit() else None, ordering_map)
            messages.success(request, f"Товар '{product.name}' обновлён")
            return redirect("account_seller_product_edit", product_id=product.id)
        if workflow == "add_document" and _save_product_document(product, document_form):
            messages.success(request, "Документ товара добавлен")
            return redirect("account_seller_product_edit", product_id=product.id)
        if workflow == "delete_document":
            document = ProductDocument.objects.filter(product=product, id=request.POST.get("document_id")).first()
            if document:
                document.delete()
                messages.success(request, "Документ удалён")
                return redirect("account_seller_product_edit", product_id=product.id)

    my_products = Product.objects.filter(seller=request.user).select_related("brand", "category").prefetch_related("images", "documents").order_by("-updated_at", "-id")[:50]
    return render(
        request,
        "account/seller_product_add.html",
        {
            "profile": profile,
            "store": getattr(request.user, "seller_store", None),
            "form": form,
            "import_form": SellerProductImportForm(),
            "bulk_form": SellerProductBulkActionForm(),
            "document_form": document_form,
            "product_obj": product,
            "my_products": my_products,
            "page_mode": "edit",
            "account_section": "seller_products",
        },
    )


@log_calls()
def account_seller_product_import_template(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/products/template/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(SELLER_PRODUCT_IMPORT_HEADERS)
    writer.writerow(["12345678", "Набор тарелок", "Servio Brand", "Посуда", "ART-001", "199.90", "25", "1", "3", "Фарфор", "Для сервировки", "Описание товара", "1", "0", "published"])
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="seller-product-import-template.csv"'
    return response


@log_calls()
def account_seller_product_export(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/products/export/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from catalog.models import Product

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "name", "brand", "category", "manufacturer_sku", "price", "stock_qty", "min_order_qty", "lead_time_days", "publication_status", "images_count", "documents_count"])
    for product in Product.objects.filter(seller=request.user).select_related("brand", "category").prefetch_related("images", "documents").order_by("id"):
        writer.writerow([product.sku, product.name, product.brand.name if product.brand_id else "", product.category.name if product.category_id else "", product.manufacturer_sku, product.price, product.stock_qty, product.min_order_qty, product.lead_time_days, product.publication_status, product.images.count(), product.documents.count()])
    response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="seller-catalog-export.csv"'
    return response


@log_calls()
def account_seller_offers(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/offers/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    store = getattr(request.user, "seller_store", None)
    if store is None:
        messages.error(request, "Сначала настройте магазин продавца")
        return redirect("account_seller_home")
    from catalog.models import SellerOffer

    form = SellerOfferForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        product = form.cleaned_data["product"]
        offer = SellerOffer.objects.filter(product=product, seller=request.user).first()
        if offer is None:
            offer = form.save()
        else:
            offer_form = SellerOfferForm(request.POST, instance=offer, user=request.user)
            if offer_form.is_valid():
                offer = offer_form.save()
        messages.success(request, f"Оффер для товара '{offer.product.name}' сохранён")
        return redirect("account_seller_offer_detail", offer_id=offer.id)

    offers = SellerOffer.objects.select_related("product", "seller_store").prefetch_related("inventories").filter(seller=request.user).order_by("-updated_at", "-id")[:100]
    return render(request, "account/seller_offers.html", {"profile": profile, "store": store, "form": form, "offers": offers, "account_section": "seller_offers"})


@log_calls()
def account_seller_offer_detail(request, offer_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/offers/{offer_id}/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import SellerInventory, SellerOffer, StockMovement

    offer = SellerOffer.objects.select_related("product", "seller_store").prefetch_related("inventories").filter(id=offer_id, seller=request.user).first()
    if not offer:
        raise Http404("Offer not found")
    offer_form = SellerOfferForm(request.POST or None, instance=offer, user=request.user, prefix="offer")
    inventory_form = SellerInventoryForm(request.POST or None, prefix="inventory")
    adjustment_form = InventoryAdjustmentForm(request.POST or None, prefix="adjust")
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "update_offer" and offer_form.is_valid():
            offer_form.save()
            messages.success(request, "Оффер обновлён")
            return redirect("account_seller_offer_detail", offer_id=offer.id)
        if action == "add_inventory" and inventory_form.is_valid():
            inventory = inventory_form.save(commit=False)
            inventory.offer = offer
            inventory.save()
            if inventory.is_primary:
                SellerInventory.objects.filter(offer=offer, is_primary=True).exclude(pk=inventory.pk).update(is_primary=False)
            messages.success(request, "Складская позиция добавлена")
            return redirect("account_seller_offer_detail", offer_id=offer.id)
    movements = StockMovement.objects.filter(inventory__offer=offer).select_related("inventory", "actor").order_by("-created_at", "-id")[:50]
    return render(request, "account/seller_offer_detail.html", {"profile": profile, "offer": offer, "offer_form": offer_form, "inventory_form": inventory_form, "adjustment_form": adjustment_form, "movements": movements, "account_section": "seller_offers"})


@log_calls()
def account_seller_warehouses(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/warehouses/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from catalog.models import SellerInventory

    inventories = SellerInventory.objects.select_related("offer", "offer__product").filter(offer__seller=request.user).order_by("warehouse_name", "offer__product__name", "id")
    warehouse_rows = {}
    for inventory in inventories:
        row = warehouse_rows.setdefault(inventory.warehouse_name, {"stock_qty": 0, "reserved_qty": 0, "incoming_qty": 0, "offers": 0, "eta_max": 0})
        row["stock_qty"] += int(inventory.stock_qty or 0)
        row["reserved_qty"] += int(inventory.reserved_qty or 0)
        row["incoming_qty"] += int(inventory.incoming_qty or 0)
        row["offers"] += 1
        row["eta_max"] = max(row["eta_max"], int(inventory.eta_days or 0))
    return render(request, "account/seller_warehouses.html", {"profile": profile, "inventories": inventories[:200], "warehouse_rows": warehouse_rows, "account_section": "seller_warehouses"})


@log_calls()
def account_seller_analytics(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/analytics/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import SellerOrder

    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    orders_qs = SellerOrder.objects.filter(seller=request.user)
    if date_from:
        orders_qs = orders_qs.filter(created_at__date__gte=date_from)
    if date_to:
        orders_qs = orders_qs.filter(created_at__date__lte=date_to)
    summary = {"orders_count": orders_qs.count(), "gmv": orders_qs.exclude(status=SellerOrder.Status.CANCELED).aggregate(total=Sum("total"))["total"] or 0, "delivered_count": orders_qs.filter(status=SellerOrder.Status.DELIVERED).count(), "avg_ticket": orders_qs.exclude(status=SellerOrder.Status.CANCELED).aggregate(avg=Avg("total"))["avg"] or 0}
    top_skus = orders_qs.values("items__product__sku", "items__name").annotate(qty=Sum("items__qty"), revenue=Sum("items__price")).order_by("-qty", "items__name")[:20]
    return render(request, "account/seller_analytics.html", {"profile": profile, "summary": summary, "top_skus": top_skus, "date_from": date_from, "date_to": date_to, "account_section": "seller_analytics"})


@log_calls()
def account_seller_payouts(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/payouts/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import SellerOrder

    store = getattr(request.user, "seller_store", None)
    commission_rate = getattr(store, "commission_rate", 0) or 0
    seller_orders = SellerOrder.objects.filter(seller=request.user).exclude(status=SellerOrder.Status.CANCELED).order_by("-created_at", "-id")[:100]
    payout_rows = []
    totals = {"gross": 0, "fee": 0, "net": 0}
    for seller_order in seller_orders:
        gross = seller_order.total
        fee = (gross * commission_rate / 100) if commission_rate else 0
        net = gross - fee
        payout_rows.append({"seller_order": seller_order, "gross": gross, "fee": fee, "net": net})
        totals["gross"] += gross
        totals["fee"] += fee
        totals["net"] += net
    return render(request, "account/seller_payouts.html", {"profile": profile, "commission_rate": commission_rate, "payout_rows": payout_rows, "totals": totals, "account_section": "seller_payouts"})


@log_calls()
def account_seller_invoices(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/invoices/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только продавцам")
        return redirect("account_home")
    from orders.models import Order, SellerOrder

    invoice_orders = SellerOrder.objects.select_related("order", "order__legal_entity").filter(seller=request.user, order__payment_method=Order.PaymentMethod.INVOICE).order_by("-created_at", "-id")[:100]
    return render(request, "account/seller_invoices.html", {"profile": profile, "invoice_orders": invoice_orders, "account_section": "seller_invoices"})


@require_POST
@log_calls()
def account_seller_inventory_delete(request, offer_id: int, inventory_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/offers/{offer_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import SellerInventory

    inventory = SellerInventory.objects.select_related("offer").filter(id=inventory_id, offer_id=offer_id, offer__seller=request.user).first()
    if not inventory:
        raise Http404("Inventory not found")
    inventory.delete()
    messages.success(request, "Складская позиция удалена")
    return redirect("account_seller_offer_detail", offer_id=offer_id)


@require_POST
@log_calls()
def account_seller_inventory_adjust(request, offer_id: int, inventory_id: int):
    if not request.user.is_authenticated:
        return redirect(f"/account/login/?next=/account/seller/offers/{offer_id}/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import SellerInventory, StockMovement

    inventory = SellerInventory.objects.select_related("offer").filter(id=inventory_id, offer_id=offer_id, offer__seller=request.user).first()
    if not inventory:
        raise Http404("Inventory not found")
    form = InventoryAdjustmentForm(request.POST, prefix="adjust")
    if not form.is_valid() or form.cleaned_data["inventory_id"] != inventory.id:
        messages.error(request, "Некорректные данные для движения по складу")
        return redirect("account_seller_offer_detail", offer_id=offer_id)
    field_map = {StockMovement.FieldType.STOCK: "stock_qty", StockMovement.FieldType.RESERVED: "reserved_qty", StockMovement.FieldType.INCOMING: "incoming_qty"}
    field_type = form.cleaned_data["field_type"]
    field_name = field_map[field_type]
    before_value = int(getattr(inventory, field_name) or 0)
    after_value = before_value + int(form.cleaned_data["delta"])
    if after_value < 0:
        messages.error(request, "Количество не может стать отрицательным")
        return redirect("account_seller_offer_detail", offer_id=offer_id)
    if field_name == "reserved_qty" and after_value > int(inventory.stock_qty or 0):
        messages.error(request, "Резерв не может быть больше остатка")
        return redirect("account_seller_offer_detail", offer_id=offer_id)
    setattr(inventory, field_name, after_value)
    inventory.save(update_fields=[field_name, "updated_at"])
    StockMovement.objects.create(inventory=inventory, field_type=field_type, delta=int(form.cleaned_data["delta"]), before_value=before_value, after_value=after_value, reason=(form.cleaned_data.get("reason") or "").strip(), actor=request.user)
    messages.success(request, "Движение по складу сохранено")
    return redirect("account_seller_offer_detail", offer_id=offer_id)


@log_calls()
def account_seller_questions(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/questions/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import ProductQuestion

    questions = ProductQuestion.objects.select_related("product", "user", "answered_by").filter(product__seller=request.user).order_by("-created_at", "-id")[:200]
    return render(request, "account/seller_questions.html", {"profile": profile, "questions": questions, "account_section": "seller_questions"})


@require_POST
@log_calls()
def account_seller_question_answer(request, question_id: int):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/questions/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import ProductQuestion

    question = ProductQuestion.objects.select_related("product").filter(id=question_id, product__seller=request.user).first()
    if not question:
        raise Http404("Question not found")
    form = SellerQuestionAnswerForm(request.POST or None, instance=question)
    if form.is_valid():
        question = form.save(commit=False)
        question.answered_by = request.user
        question.answered_at = timezone.now()
        question.save(update_fields=["answer_text", "is_public", "answered_by", "answered_at", "updated_at"])
        messages.success(request, "Ответ на вопрос сохранён")
    else:
        messages.error(request, "Не удалось сохранить ответ")
    return redirect("account_seller_questions")


@log_calls()
def account_seller_reviews(request):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/reviews/")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import ProductReview, ProductReviewComment

    reviews = (
        ProductReview.objects.select_related("product", "user", "user__profile")
        .prefetch_related(Prefetch("comments", queryset=ProductReviewComment.objects.select_related("user").order_by("created_at", "id")))
        .filter(product__seller=request.user)
        .order_by("-created_at", "-id")[:200]
    )
    reply_forms = {}
    for review in reviews:
        existing_reply = next((comment for comment in review.comments.all() if comment.user_id == request.user.id), None)
        reply_forms[review.id] = SellerReviewReplyForm(prefix=f"review-{review.id}", instance=existing_reply, initial={"text": getattr(existing_reply, "text", "")})
    return render(request, "account/seller_reviews.html", {"profile": profile, "reviews": reviews, "reply_forms": reply_forms, "account_section": "seller_reviews"})


@require_POST
@log_calls()
def account_seller_review_reply(request, review_id: int):
    if not request.user.is_authenticated:
        return redirect("/account/login/?next=/account/seller/reviews/")
    if not _is_seller(request):
        messages.error(request, "Раздел доступен только пользователям с ролью 'Продавец'")
        return redirect("account_home")
    from catalog.models import ProductReview, ProductReviewComment

    review = ProductReview.objects.select_related("product").filter(id=review_id, product__seller=request.user).first()
    if not review:
        raise Http404("Review not found")
    existing_reply = ProductReviewComment.objects.filter(review=review, user=request.user).order_by("id").first()
    form = SellerReviewReplyForm(request.POST, prefix=f"review-{review.id}", instance=existing_reply)
    if form.is_valid():
        reply = form.save(commit=False)
        reply.review = review
        reply.user = request.user
        reply.save()
        messages.success(request, "Ответ на отзыв сохранён")
    else:
        messages.error(request, "Не удалось сохранить ответ на отзыв")
    return redirect("account_seller_reviews")
