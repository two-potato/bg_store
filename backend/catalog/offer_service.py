from __future__ import annotations

from decimal import Decimal

from django.db.models import Prefetch

from .models import Product, SellerInventory, SellerOffer


def active_offer_queryset():
    return (
        SellerOffer.objects.filter(status=SellerOffer.Status.ACTIVE)
        .select_related("seller", "seller_store")
        .prefetch_related(
            Prefetch(
                "inventories",
                queryset=SellerInventory.objects.order_by("-is_primary", "warehouse_name", "id"),
            )
        )
        .order_by("-is_featured", "price", "id")
    )


def resolve_product_offer(product: Product) -> SellerOffer | None:
    prefetched = getattr(product, "_prefetched_objects_cache", {}).get("seller_offers")
    offers = prefetched if prefetched is not None else list(active_offer_queryset().filter(product_id=product.id))
    if not offers:
        return None
    in_stock = [offer for offer in offers if offer.available_stock_qty > 0]
    ordered = in_stock or list(offers)
    return ordered[0] if ordered else None


def apply_offer_snapshot(products) -> list[Product]:
    prepared = list(products)
    for product in prepared:
        offer = resolve_product_offer(product)
        if offer is None:
            product._active_offer = None
            product._effective_price = product.price
            product._effective_stock_qty = max(0, int(product.stock_qty or 0))
            product._effective_lead_time_days = max(0, int(product.lead_time_days or 0))
            product._effective_min_order_qty = max(1, int(product.min_order_qty or 1))
            continue
        inventories = list(getattr(offer, "_prefetched_objects_cache", {}).get("inventories", []) or [])
        stock_qty = offer.available_stock_qty
        lead_time = offer.lead_time_days
        if inventories:
            lead_time = min([max(0, int(inv.eta_days or 0)) for inv in inventories] + [max(0, int(offer.lead_time_days or 0))])
        product._active_offer = offer
        product._effective_price = Decimal(str(offer.price)).quantize(Decimal("0.01"))
        product._effective_stock_qty = max(0, stock_qty)
        product._effective_lead_time_days = max(0, lead_time)
        product._effective_min_order_qty = max(1, int(offer.min_order_qty or 1))
    return prepared
