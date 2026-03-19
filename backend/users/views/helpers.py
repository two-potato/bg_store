from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import Http404, FileResponse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.db.models import Q, Prefetch, Count, Sum, Avg
from django.db import transaction
from django.utils.text import slugify
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from io import StringIO, TextIOWrapper
import csv
import hashlib
import secrets
import requests
from ..forms import (
    LoginForm,
    RegisterForm,
    ProfileForm,
    NotificationPreferencesForm,
    LegalEntityRequestForm,
    AddressForm,
    SellerStoreForm,
    SellerProductCreateForm,
    SellerProductImportForm,
    SellerProductBulkActionForm,
    SellerOfferForm,
    SellerInventoryForm,
    InventoryAdjustmentForm,
    SellerQuestionAnswerForm,
    SellerReviewReplyForm,
    CompanyMemberInviteForm,
    CompanyMemberUpdateForm,
    ApprovalPolicyForm,
    CompanySettingsForm,
    CompanyContactForm,
    ProductDocumentForm,
    OrderClaimForm,
    OrderClaimUpdateForm,
    ShipmentCreateForm,
    SellerOrderItemCancelForm,
    OrderSupportTicketForm,
    OrderSupportTicketUpdateForm,
)
from ..api.views import verify_init_data
from core.logging_utils import log_calls
from core.notifications import send_mail_message
import logging
from ..models import UserProfile
from shopfront.cart_store import merge_session_cart_with_persistent
from commerce.company_service import ensure_company_workspace, approver_memberships_for_company, ensure_approval_policy

log = logging.getLogger("users")


User = get_user_model()


SELLER_PRODUCT_IMPORT_HEADERS = [
    "sku",
    "name",
    "brand",
    "category",
    "manufacturer_sku",
    "price",
    "stock_qty",
    "min_order_qty",
    "lead_time_days",
    "material",
    "purpose",
    "description",
    "is_new",
    "is_promo",
    "publication_status",
]


def _approver_company_ids(user):
    from commerce.company_service import sync_company_membership_from_legal_entity
    from commerce.models import CompanyMembership, LegalEntityMembership, MembershipRole

    company_ids = set(
        CompanyMembership.objects.filter(
            user=user,
            role__in=[
                CompanyMembership.Role.OWNER,
                CompanyMembership.Role.ADMIN,
                CompanyMembership.Role.APPROVER,
            ],
        ).values_list("company_id", flat=True)
    )
    managed_memberships = (
        LegalEntityMembership.objects.select_related("legal_entity", "role")
        .filter(user=user, role__code__in=["owner", "admin"])
    )
    for membership in managed_memberships:
        company_ids.add(sync_company_membership_from_legal_entity(membership).company_id)
    return company_ids


def _visible_orders_queryset(user):
    from orders.models import Order
    from catalog.models import ProductImage
    from orders.models import OrderItem

    item_qs = OrderItem.objects.select_related("product").prefetch_related(
        Prefetch(
            "product__images",
            queryset=ProductImage.objects.only("id", "product_id", "url", "ordering").order_by("ordering", "id"),
            to_attr="prefetched_images",
        )
    )
    return (
        Order.objects.filter(
            Q(placed_by=user) | Q(legal_entity__company__id__in=_approver_company_ids(user))
        )
        .select_related("legal_entity", "delivery_address", "placed_by", "requested_by", "approved_by")
        .prefetch_related("seller_splits", Prefetch("items", queryset=item_qs))
        .distinct()
    )


def _notification_feed(user, limit: int = 80):
    from orders.models import Order, OrderClaim, OrderSupportTicket

    events = []
    orders = (
        _visible_orders_queryset(user)
        .select_related("legal_entity")
        .order_by("-updated_at", "-id")[:limit]
    )
    for order in orders:
        events.append(
            {
                "at": order.updated_at,
                "title": f"Заказ #{order.id}",
                "subtitle": f"{order.get_status_display()} · {order.total} ₽",
                "href": reverse("account_order_detail", kwargs={"order_id": order.id}),
            }
        )
    claims = (
        OrderClaim.objects.select_related("order", "created_by", "responded_by")
        .filter(Q(order__placed_by=user) | Q(order__seller_orders__seller=user))
        .distinct()
        .order_by("-updated_at", "-id")[:limit]
    )
    for claim in claims:
        events.append(
            {
                "at": claim.updated_at,
                "title": f"Диспут по заказу #{claim.order_id}",
                "subtitle": f"{claim.get_status_display()} · {claim.get_claim_type_display()}",
                "href": reverse("account_order_detail", kwargs={"order_id": claim.order_id}),
            }
        )
    tickets = (
        OrderSupportTicket.objects.select_related("order", "created_by")
        .filter(Q(order__placed_by=user) | Q(order__seller_orders__seller=user))
        .distinct()
        .order_by("-updated_at", "-id")[:limit]
    )
    for ticket in tickets:
        events.append(
            {
                "at": ticket.updated_at,
                "title": f"Support ticket по заказу #{ticket.order_id}",
                "subtitle": f"{ticket.get_status_display()} · {ticket.subject}",
                "href": reverse("account_order_detail", kwargs={"order_id": ticket.order_id}),
            }
        )
    return sorted(events, key=lambda row: row["at"], reverse=True)[:limit]


def _company_workspace_rows(user, memberships):
    from commerce.models import ApprovalPolicy, Company, CompanyMembership, MembershipRole

    memberships = list(memberships)
    if not memberships:
        return []

    legal_entities = [membership.legal_entity for membership in memberships]
    legal_entity_ids = [entity.id for entity in legal_entities]
    existing_companies = {
        company.legal_entity_id: company
        for company in Company.objects.filter(legal_entity_id__in=legal_entity_ids).select_related("approval_policy", "legal_entity")
    }
    missing_companies = [
        Company(legal_entity=entity, display_name=entity.name)
        for entity in legal_entities
        if entity.id not in existing_companies
    ]
    if missing_companies:
        Company.objects.bulk_create(missing_companies)
        existing_companies = {
            company.legal_entity_id: company
            for company in Company.objects.filter(legal_entity_id__in=legal_entity_ids).select_related("approval_policy", "legal_entity")
        }

    role_map = {
        "owner": CompanyMembership.Role.OWNER,
        "admin": CompanyMembership.Role.ADMIN,
        "manager": CompanyMembership.Role.BUYER,
    }
    existing_memberships = {
        (membership.company_id, membership.user_id): membership
        for membership in CompanyMembership.objects.filter(
            user=user,
            company_id__in=[company.id for company in existing_companies.values()],
        )
    }
    roles_by_id = {
        role.id: role.code
        for role in MembershipRole.objects.filter(
            id__in=[membership.role_id for membership in memberships if membership.role_id]
        )
    }
    memberships_to_create = []
    memberships_to_update = []
    companies = []
    for membership in memberships:
        company = existing_companies[membership.legal_entity_id]
        role_code = roles_by_id.get(membership.role_id, "buyer")
        desired_role = role_map.get(str(role_code), CompanyMembership.Role.BUYER)
        existing_membership = existing_memberships.get((company.id, user.id))
        if existing_membership is None:
            memberships_to_create.append(
                CompanyMembership(user=user, company=company, role=desired_role)
            )
        elif existing_membership.role != desired_role:
            existing_membership.role = desired_role
            memberships_to_update.append(existing_membership)
        companies.append((membership, company))

    if memberships_to_create:
        CompanyMembership.objects.bulk_create(memberships_to_create)
    if memberships_to_update:
        CompanyMembership.objects.bulk_update(memberships_to_update, ["role"])

    membership_map = {
        membership.company_id: membership
        for membership in CompanyMembership.objects.filter(
            user=user,
            company_id__in=[company.id for _, company in companies],
        )
    }
    policies_by_company_id = {
        policy.company_id: policy
        for policy in ApprovalPolicy.objects.filter(company_id__in=[company.id for _, company in companies])
    }
    missing_policy_company_ids = [
        company.id
        for _, company in companies
        if company.id not in policies_by_company_id
    ]
    if missing_policy_company_ids:
        ApprovalPolicy.objects.bulk_create(
            [ApprovalPolicy(company_id=company_id) for company_id in missing_policy_company_ids],
            ignore_conflicts=True,
        )
        policies_by_company_id = {
            policy.company_id: policy
            for policy in ApprovalPolicy.objects.filter(company_id__in=[company.id for _, company in companies])
        }
    rows = []
    for legal_membership, company in companies:
        rows.append(
            {
                "company": company,
                "policy": policies_by_company_id.get(company.id),
                "membership": membership_map.get(company.id),
                "legal_membership": legal_membership,
            }
        )
    return rows


def _visible_seller_orders_queryset(user):
    from orders.models import SellerOrder, SellerOrderItem, Shipment, ShipmentItem
    from catalog.models import ProductImage

    item_qs = SellerOrderItem.objects.select_related("product", "seller_offer").prefetch_related(
        Prefetch(
            "product__images",
            queryset=ProductImage.objects.only("id", "product_id", "url", "ordering").order_by("ordering", "id"),
            to_attr="prefetched_images",
        )
    )
    shipment_item_qs = ShipmentItem.objects.select_related("seller_order_item").order_by("id")
    shipment_qs = Shipment.objects.prefetch_related(Prefetch("items", queryset=shipment_item_qs)).order_by("-created_at", "-id")
    return (
        SellerOrder.objects.filter(seller=user)
        .select_related("order", "order__legal_entity", "order__delivery_address", "order__placed_by")
        .prefetch_related(
            Prefetch("items", queryset=item_qs),
            Prefetch("shipments", queryset=shipment_qs),
        )
        .order_by("-created_at", "-id")
    )


def _sync_parent_order_status_from_seller_orders(order):
    from orders.models import SellerOrder, Shipment

    seller_orders = list(order.seller_orders.all())
    if not seller_orders:
        return
    statuses = {seller_order.status for seller_order in seller_orders}
    shipments = list(Shipment.objects.filter(seller_order__order=order))
    shipment_statuses = {shipment.status for shipment in shipments}
    new_status = order.status
    if statuses == {SellerOrder.Status.CANCELED}:
        new_status = order.Status.CANCELED
    elif statuses == {SellerOrder.Status.DELIVERED}:
        new_status = order.Status.DELIVERED
    elif statuses & {SellerOrder.Status.ACCEPTED, SellerOrder.Status.PICKING, SellerOrder.Status.SHIPPED, SellerOrder.Status.DELIVERED}:
        new_status = order.Status.DELIVERING
    elif shipment_statuses & {Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED}:
        new_status = order.Status.DELIVERING
    if new_status != order.status:
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])


def _managed_company_queryset(user):
    from commerce.models import Company, CompanyMembership

    return Company.objects.filter(
        memberships__user=user,
        memberships__role__in=[CompanyMembership.Role.OWNER, CompanyMembership.Role.ADMIN],
    ).distinct()


def _approval_required_count(order) -> int:
    company = ensure_company_workspace(order.legal_entity) if getattr(order, "legal_entity_id", None) else None
    if not company:
        return 1
    from commerce.company_service import ensure_approval_policy

    policy = ensure_approval_policy(company)
    required = int(getattr(policy, "required_approvals_count", 1) or 1)
    return max(1, required)


def _approval_approved_count(order) -> int:
    from orders.models import OrderApprovalLog

    return (
        OrderApprovalLog.objects.filter(order=order, decision=OrderApprovalLog.Decision.APPROVED)
        .values("actor_id")
        .distinct()
        .count()
    )


def _can_manage_product(user, product) -> bool:
    if not user or not user.is_authenticated:
        return False
    return bool(user.is_superuser or user.is_staff or getattr(product, "seller_id", None) == user.id)


def _is_marketplace_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and str(profile.role) == str(UserProfile.Role.ADMIN))


def _seller_order_allocation_maps(seller_order):
    from orders.models import Shipment

    shipment_allocations: dict[int, dict[int, int]] = {}
    item_allocated: dict[int, int] = {}
    item_locked: dict[int, int] = {}
    delivered_qty: dict[int, int] = {}
    in_transit_qty: dict[int, int] = {}

    for shipment in seller_order.shipments.all():
        current = shipment_allocations.setdefault(shipment.id, {})
        for shipment_item in shipment.items.all():
            qty = int(shipment_item.qty or 0)
            if qty <= 0:
                continue
            seller_order_item_id = shipment_item.seller_order_item_id
            current[seller_order_item_id] = qty
            item_allocated[seller_order_item_id] = item_allocated.get(seller_order_item_id, 0) + qty
            if shipment.status in {Shipment.Status.IN_TRANSIT, Shipment.Status.DELIVERED}:
                item_locked[seller_order_item_id] = item_locked.get(seller_order_item_id, 0) + qty
            if shipment.status == Shipment.Status.IN_TRANSIT:
                in_transit_qty[seller_order_item_id] = in_transit_qty.get(seller_order_item_id, 0) + qty
            if shipment.status == Shipment.Status.DELIVERED:
                delivered_qty[seller_order_item_id] = delivered_qty.get(seller_order_item_id, 0) + qty

    item_remaining: dict[int, int] = {}
    for item in seller_order.items.all():
        item_remaining[item.id] = max(0, int(item.active_qty) - item_allocated.get(item.id, 0))

    return {
        "shipment_allocations": shipment_allocations,
        "item_allocated": item_allocated,
        "item_locked": item_locked,
        "item_remaining": item_remaining,
        "item_in_transit": in_transit_qty,
        "item_delivered": delivered_qty,
    }


def _sync_seller_order_fulfillment_status(seller_order):
    total_active_qty = sum(int(item.active_qty) for item in seller_order.items.all())
    allocations = _seller_order_allocation_maps(seller_order)
    delivered_qty = sum(allocations["item_delivered"].values())
    transit_qty = sum(allocations["item_in_transit"].values())

    update_fields = ["updated_at"]
    if total_active_qty == 0:
        if seller_order.status != "canceled":
            seller_order.status = "canceled"
            update_fields.append("status")
        seller_order.save(update_fields=update_fields)
        return seller_order

    if delivered_qty >= total_active_qty:
        seller_order.status = "delivered"
        seller_order.delivered_at = seller_order.delivered_at or timezone.now()
        update_fields.extend(["status", "delivered_at"])
    elif (delivered_qty + transit_qty) > 0:
        seller_order.status = "shipped"
        seller_order.shipped_at = seller_order.shipped_at or timezone.now()
        update_fields.extend(["status", "shipped_at"])
    seller_order.save(update_fields=list(dict.fromkeys(update_fields)))
    return seller_order


def _save_uploaded_product_images(product, uploaded_files):
    from catalog.models import ProductImage

    created = 0
    if not uploaded_files:
        return created
    existing_count = product.images.count()
    for index, upload in enumerate(uploaded_files, start=1):
        if existing_count + created >= 10:
            break
        extension = ""
        if "." in (upload.name or ""):
            extension = "." + upload.name.rsplit(".", 1)[-1].lower()
        filename = slugify(upload.name.rsplit(".", 1)[0] or f"product-{product.id}") or f"product-{product.id}"
        path = default_storage.save(
            f"product_gallery/{product.id}/{timezone.now().strftime('%Y%m%d%H%M%S')}-{filename}-{index}{extension}",
            upload,
        )
        ProductImage.objects.create(
            product=product,
            url=f"/media/{path}",
            alt=product.name,
            ordering=product.images.count() + 1,
        )
        created += 1
    return created


def _parse_import_bool(raw_value) -> bool:
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _import_seller_products_from_csv(*, user, uploaded_file):
    from decimal import Decimal, InvalidOperation
    from catalog.models import Product, Brand, Category

    uploaded_file.seek(0)
    text_stream = TextIOWrapper(uploaded_file.file, encoding="utf-8-sig")
    reader = csv.DictReader(text_stream)
    headers = reader.fieldnames or []
    required_headers = [header for header in SELLER_PRODUCT_IMPORT_HEADERS if header != "publication_status"]
    missing_headers = [header for header in required_headers if header not in headers]
    if missing_headers:
        return {
            "created": 0,
            "updated": 0,
            "errors": [f"В CSV не хватает колонок: {', '.join(missing_headers)}"],
            "rows": 0,
        }

    created = 0
    updated = 0
    errors: list[str] = []
    rows = 0

    for row_index, row in enumerate(reader, start=2):
        rows += 1
        sku = str(row.get("sku") or "").strip()
        name = str(row.get("name") or "").strip()
        brand_name = str(row.get("brand") or "").strip()
        category_name = str(row.get("category") or "").strip()
        if not sku or not name or not brand_name or not category_name:
            errors.append(f"Строка {row_index}: обязательны sku, name, brand, category")
            continue
        if not (sku.isdigit() and len(sku) == 8):
            errors.append(f"Строка {row_index}: SKU должен состоять из 8 цифр")
            continue
        try:
            price = Decimal(str(row.get('price') or '0').strip() or "0")
        except (InvalidOperation, ValueError):
            errors.append(f"Строка {row_index}: некорректная цена")
            continue
        int_fields = {}
        for field_name in ("stock_qty", "min_order_qty", "lead_time_days"):
            raw_value = str(row.get(field_name) or "").strip() or "0"
            try:
                int_fields[field_name] = int(raw_value)
            except ValueError:
                errors.append(f"Строка {row_index}: поле {field_name} должно быть числом")
                int_fields = None
                break
        if int_fields is None:
            continue
        if int_fields["stock_qty"] < 0 or int_fields["min_order_qty"] < 1 or int_fields["lead_time_days"] < 0:
            errors.append(f"Строка {row_index}: stock_qty >= 0, min_order_qty >= 1, lead_time_days >= 0")
            continue

        brand, _ = Brand.objects.get_or_create(name=brand_name)
        category, _ = Category.objects.get_or_create(name=category_name)
        product = Product.objects.filter(sku=sku, seller=user).first()
        is_created = product is None
        if product is None:
            product = Product(sku=sku, seller=user)
        product.name = name
        product.brand = brand
        product.category = category
        product.manufacturer_sku = str(row.get("manufacturer_sku") or "").strip()
        product.price = price
        product.stock_qty = int_fields["stock_qty"]
        product.min_order_qty = int_fields["min_order_qty"]
        product.lead_time_days = int_fields["lead_time_days"]
        product.material = str(row.get("material") or "").strip()
        product.purpose = str(row.get("purpose") or "").strip()
        product.description = str(row.get("description") or "").strip()
        product.is_new = _parse_import_bool(row.get("is_new"))
        product.is_promo = _parse_import_bool(row.get("is_promo"))
        publication_status = str(row.get("publication_status") or Product.PublicationStatus.PUBLISHED).strip() or Product.PublicationStatus.PUBLISHED
        if publication_status not in {choice[0] for choice in Product.PublicationStatus.choices}:
            errors.append(f"Строка {row_index}: publication_status должен быть draft/published/archived")
            continue
        product.publication_status = publication_status
        try:
            product.full_clean()
            product.save()
        except (ValidationError, ValueError) as exc:
            errors.append(f"Строка {row_index}: {exc}")
            continue
        if is_created:
            created += 1
        else:
            updated += 1

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
        "rows": rows,
    }


def _save_linked_product_images(product, image_urls):
    from catalog.models import ProductImage

    created = 0
    existing_urls = set(product.images.values_list("url", flat=True))
    existing_count = product.images.count()
    for url in image_urls or []:
        if existing_count + created >= 10:
            break
        if url in existing_urls:
            continue
        ProductImage.objects.create(
            product=product,
            url=url,
            alt=product.name,
            ordering=product.images.count() + 1,
        )
        existing_urls.add(url)
        created += 1
    return created


def _reorder_product_images(product, primary_image_id: int | None, ordering_map: dict[int, int]):
    from catalog.models import ProductImage

    for image in ProductImage.objects.filter(product=product):
        image.is_primary = bool(primary_image_id and image.id == primary_image_id)
        if image.id in ordering_map:
            image.ordering = max(0, int(ordering_map[image.id]))
        image.save(update_fields=["is_primary", "ordering", "updated_at"])


def _save_product_document(product, form: ProductDocumentForm) -> bool:
    if not form.is_valid():
        return False
    doc = form.save(commit=False)
    doc.product = product
    doc.ordering = product.documents.count() + 1
    doc.save()
    return True


def _is_seller(request) -> bool:
    profile = getattr(request.user, "profile", None)
    if not profile:
        return False
    seller_value = getattr(getattr(UserProfile, "Role", object), "SELLER", "seller")
    return str(profile.role) == str(seller_value)
