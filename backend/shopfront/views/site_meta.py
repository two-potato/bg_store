"""Site metadata endpoints such as robots.txt and sitemap.xml."""

from __future__ import annotations

from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, Category, Collection, Product
from commerce.models import SellerStore
from core.logging_utils import log_calls
from users.models import UserProfile

from .constants import log
from .utils_catalog import _category_path


@log_calls(log)
def robots_txt(request):
    """Render robots.txt for crawlers with sitemap reference."""
    host = request.get_host().split(":")[0]
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /api/docs/",
        "Disallow: /api/schema/",
        "Disallow: /account/",
        "Disallow: /checkout/",
        "Disallow: /payments/fake/",
        "Disallow: /metrics",
        "Disallow: /metrics/",
        f"Sitemap: https://{host}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@log_calls(log)
def sitemap_xml(request):
    """Render dynamic XML sitemap for major shopfront entities."""
    host = request.get_host().split(":")[0]
    base = f"https://{host}"
    static_entries = [
        (reverse("home"), timezone.now()),
        (reverse("catalog"), timezone.now()),
        (reverse("products"), timezone.now()),
        (reverse("categories"), timezone.now()),
        (reverse("vendors"), timezone.now()),
        (reverse("search"), timezone.now()),
        (reverse("buyers"), timezone.now()),
        (reverse("suppliers"), timezone.now()),
        (reverse("brands"), timezone.now()),
        (reverse("promotions"), timezone.now()),
        (reverse("blog"), timezone.now()),
        (reverse("about"), timezone.now()),
        (reverse("delivery"), timezone.now()),
        (reverse("payment"), timezone.now()),
        (reverse("returns"), timezone.now()),
        (reverse("faq"), timezone.now()),
        (reverse("contacts"), timezone.now()),
    ]
    urls = [(base + path, updated_at) for path, updated_at in static_entries]
    urls.extend(
        [
            (base + reverse("product", kwargs={"slug": slug}), updated_at)
            for slug, updated_at in Product.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    categories = list(
        Category.objects.select_related("parent")
        .exclude(slug="")
        .only("slug", "parent_id", "updated_at")
    )
    urls.extend(
        [
            (base + reverse("category_detail", kwargs={"category_slug": _category_path(category)}), category.updated_at)
            for category in categories
            if _category_path(category)
        ]
    )
    urls.extend(
        [
            (base + reverse("vendor_detail", kwargs={"vendor_slug": slug}), updated_at)
            for slug, updated_at in SellerStore.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    profile_lastmod = timezone.now()
    urls.extend(
        [
            (base + reverse("vendor_detail", kwargs={"vendor_slug": slug}), profile_lastmod)
            for slug in UserProfile.objects.exclude(slug="").exclude(user__seller_store__isnull=False).values_list("slug", flat=True)[:50000]
        ]
    )
    urls.extend(
        [
            (base + reverse("brand_detail", kwargs={"brand_slug": slug}), updated_at)
            for slug, updated_at in Brand.objects.exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )
    urls.extend(
        [
            (base + reverse("collection_detail", kwargs={"collection_slug": slug}), updated_at)
            for slug, updated_at in Collection.objects.filter(is_active=True).exclude(slug="").values_list("slug", "updated_at")[:50000]
        ]
    )

    body = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">",
    ]
    for loc, lastmod in urls:
        body.append(
            f"  <url><loc>{escape(loc)}</loc><lastmod>{lastmod.date().isoformat()}</lastmod></url>"
        )
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml; charset=utf-8")
