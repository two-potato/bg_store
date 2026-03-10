from collections import OrderedDict
from decimal import Decimal

from django.utils import timezone

from .models import Order, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment, ShipmentItem


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
                },
            )
            existing_item_ids.append(seller_order_item.id)
        SellerOrderItem.objects.filter(seller_order=seller_order).exclude(id__in=existing_item_ids).delete()
        if not seller_order.shipments.exists() and seller_order.items.exists():
            shipment = Shipment.objects.create(
                seller_order=seller_order,
                warehouse_name=payload["seller_store_name"] or "Основной склад",
                delivery_method="marketplace_split",
                status=Shipment.Status.DRAFT,
            )
            ShipmentItem.objects.bulk_create(
                [
                    ShipmentItem(shipment=shipment, seller_order_item=seller_order_item, qty=seller_order_item.qty)
                    for seller_order_item in seller_order.items.all()
                ]
            )

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
