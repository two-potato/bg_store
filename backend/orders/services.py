from collections import OrderedDict
from decimal import Decimal

from django.utils import timezone

from .models import Order, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment, ShipmentItem


def recalc_seller_order_totals(seller_order: SellerOrder) -> SellerOrder:
    active_subtotal = sum(
        (Decimal(str(item.price)) * Decimal(int(item.active_qty)) for item in seller_order.items.all()),
        start=Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    seller_order.subtotal = active_subtotal
    seller_order.total = max(Decimal("0.00"), active_subtotal - Decimal(str(seller_order.discount_amount or 0))).quantize(Decimal("0.01"))
    seller_order.save(update_fields=["subtotal", "total", "updated_at"])
    return seller_order


def recalc_order_totals_from_items(order: Order) -> Order:
    order.recalc_totals(explicit_discount_amount=order.discount_amount)
    order.save(update_fields=["subtotal", "discount_amount", "total", "updated_at"])
    return order


def trim_shipment_allocations(seller_order_item: SellerOrderItem) -> None:
    max_allocated = seller_order_item.active_qty
    shipment_items = list(
        seller_order_item.shipment_items.select_related("shipment").order_by(
            "shipment__status",
            "shipment__created_at",
            "shipment_id",
        )
    )
    allocated = sum(int(item.qty or 0) for item in shipment_items)
    overflow = max(0, allocated - max_allocated)
    if overflow <= 0:
        return
    for shipment_item in reversed(shipment_items):
        if overflow <= 0:
            break
        reducible = min(int(shipment_item.qty or 0), overflow)
        if reducible <= 0:
            continue
        shipment_item.qty -= reducible
        overflow -= reducible
        if shipment_item.qty > 0:
            shipment_item.save(update_fields=["qty", "updated_at"])
        else:
            shipment_item.delete()


def plan_seller_splits(order: Order) -> list[OrderSellerSplit]:
    groups: OrderedDict[int, dict] = OrderedDict()
    items = order.items.select_related(
        "product__seller",
        "product__seller__seller_store",
        "seller_offer__seller",
        "seller_offer__seller_store",
    ).all()

    for item in items:
        seller = getattr(getattr(item, "seller_offer", None), "seller", None) or getattr(item.product, "seller", None)
        if seller is None:
            continue
        seller_store = getattr(getattr(item, "seller_offer", None), "seller_store", None) or getattr(seller, "seller_store", None)
        bucket = groups.setdefault(
            seller.id,
            {
                "seller": seller,
                "seller_store_name": getattr(seller_store, "name", "") or "",
                "items_count": 0,
                "subtotal": Decimal("0.00"),
                "items": [],
            },
        )
        bucket["items_count"] += int(item.qty or 0)
        bucket["subtotal"] += (Decimal(str(item.price)) * Decimal(int(item.qty or 0))).quantize(Decimal("0.01"))
        bucket["items"].append(item)

    OrderSellerSplit.objects.filter(order=order).exclude(seller_id__in=list(groups.keys())).delete()
    SellerOrder.objects.filter(order=order).exclude(seller_id__in=list(groups.keys())).delete()

    splits: list[OrderSellerSplit] = []
    for payload in groups.values():
        split, _created = OrderSellerSplit.objects.update_or_create(
            order=order,
            seller=payload["seller"],
            defaults={
                "seller_store_name": payload["seller_store_name"],
                "items_count": payload["items_count"],
                "subtotal": payload["subtotal"],
                "status": OrderSellerSplit.Status.READY if len(groups) > 1 else OrderSellerSplit.Status.PLANNED,
            },
        )
        splits.append(split)

        seller_order, _created = SellerOrder.objects.update_or_create(
            order=order,
            seller=payload["seller"],
            defaults={
                "seller_store_name": payload["seller_store_name"],
                "customer_comment": order.customer_comment or "",
                "subtotal": payload["subtotal"],
                "discount_amount": Decimal("0.00"),
                "total": payload["subtotal"],
            },
        )
        existing_item_ids = []
        for item in payload["items"]:
            seller_order_item, _ = SellerOrderItem.objects.update_or_create(
                order_item=item,
                defaults={
                    "seller_order": seller_order,
                    "product": item.product,
                    "seller_offer": getattr(item, "seller_offer", None),
                    "name": item.name,
                    "price": item.price,
                    "qty": item.qty,
                    "canceled_qty": getattr(item, "canceled_qty", 0) or 0,
                },
            )
            existing_item_ids.append(seller_order_item.id)
        SellerOrderItem.objects.filter(seller_order=seller_order).exclude(id__in=existing_item_ids).delete()
        if not seller_order.shipments.exists() and seller_order.items.exists():
            Shipment.objects.create(
                seller_order=seller_order,
                warehouse_name=payload["seller_store_name"] or "Основной склад",
                delivery_method="marketplace_split",
                status=Shipment.Status.DRAFT,
            )
        recalc_seller_order_totals(seller_order)

    next_status = Order.SplitStatus.SINGLE if len(splits) <= 1 else Order.SplitStatus.PLANNED
    if order.split_status != next_status:
        Order.objects.filter(pk=order.pk).update(split_status=next_status)
        order.split_status = next_status

    return splits


def mark_seller_order_status(seller_order: SellerOrder, status: str) -> SellerOrder:
    seller_order.status = status
    now = timezone.now()
    update_fields = ["status", "updated_at"]
    if status == SellerOrder.Status.ACCEPTED and not seller_order.accepted_at:
        seller_order.accepted_at = now
        update_fields.append("accepted_at")
    if status == SellerOrder.Status.SHIPPED and not seller_order.shipped_at:
        seller_order.shipped_at = now
        update_fields.append("shipped_at")
    if status == SellerOrder.Status.DELIVERED and not seller_order.delivered_at:
        seller_order.delivered_at = now
        update_fields.append("delivered_at")
    seller_order.save(update_fields=update_fields)
    return seller_order
