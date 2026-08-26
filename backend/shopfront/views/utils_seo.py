"""SEO and rich-snippet helper utilities for shopfront views."""

from __future__ import annotations

import json

from django.urls import reverse

from catalog.models import Product, normalize_public_media_url
from commerce.models import SellerStore


def _absolute_url(request, path: str) -> str:
    """Build an absolute URL normalized for public media routing."""
    return request.build_absolute_uri(normalize_public_media_url(path))


def _truncate_text(value: str, limit: int = 160) -> str:
    """Truncate text to a bounded length suitable for metadata fields."""
    text = (value or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _default_og_image(request) -> str:
    """Return the default Open Graph image URL for shopfront pages."""
    return _absolute_url(request, "/static/shopfront/big_logo.png")


def _product_primary_image(product: Product):
    """Return the primary product image, preferring prefetched payload."""
    prefetched = getattr(product, "prefetched_images", None)
    if prefetched is not None:
        return prefetched[0] if prefetched else None
    images = list(product.images.all())
    return images[0] if images else None


def _seo_context(
    request,
    *,
    title: str,
    description: str,
    canonical: str | None = None,
    robots: str = "index,follow",
    og_type: str = "website",
    og_image: str | None = None,
    json_ld: dict | list | None = None,
):
    """Build standard SEO context keys consumed by base templates."""
    canonical_url = canonical or _absolute_url(request, request.path)
    context = {
        "seo_title": title,
        "seo_description": _truncate_text(description, 170),
        "seo_canonical": canonical_url,
        "seo_robots": robots,
        "seo_og_type": og_type,
        "seo_og_image": og_image or _default_og_image(request),
    }
    if json_ld is not None:
        context["seo_json_ld"] = json.dumps(json_ld, ensure_ascii=False)
    return context


def _website_json_ld(request):
    """Return JSON-LD metadata for the website entity."""
    base = _absolute_url(request, "/")
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Servio",
        "url": base,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{base}search/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }


def _organization_json_ld(request):
    """Return JSON-LD metadata for the Servio organization entity."""
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Servio",
        "url": _absolute_url(request, "/"),
        "logo": _absolute_url(request, "/static/shopfront/favicon.svg"),
        "contactPoint": [
            {
                "@type": "ContactPoint",
                "contactType": "customer support",
                "email": "hello@servio.market",
                "telephone": "+7-495-120-42-20",
                "availableLanguage": ["ru"],
            }
        ],
    }


def _product_json_ld(request, product: Product, seller_store: SellerStore | None = None):
    """Return JSON-LD metadata for a product detail page."""
    images = []
    for img in getattr(product, "prefetched_images", None) or product.images.all():
        try:
            images.append(_absolute_url(request, img.url))
        except Exception:
            continue
    if not images:
        images.append(_default_og_image(request))
    price = getattr(product, "display_price", None) or product.price
    stock_qty = getattr(product, "display_stock_qty", None)
    if stock_qty is None:
        stock_qty = product.stock_qty
    availability = "https://schema.org/InStock" if (stock_qty or 0) > 0 else "https://schema.org/OutOfStock"
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "sku": product.sku or "",
        "image": images,
        "description": _truncate_text(product.description or f"{product.name} в каталоге Servio для профессиональных закупок HoReCa.", 300),
        "brand": {"@type": "Brand", "name": getattr(product.brand, "name", "") or ""},
        "offers": {
            "@type": "Offer",
            "priceCurrency": "RUB",
            "price": str(price),
            "availability": availability,
            "url": _absolute_url(request, reverse("product", kwargs={"slug": product.slug})),
        },
    }
    if seller_store:
        data["seller"] = {"@type": "Organization", "name": seller_store.name}
    return data
