import re
import time
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand
from catalog.models import Brand, Category, Product, ProductImage, Tag


BASE = "https://restinternational.ru"
HEADERS = {"User-Agent": "bgshop-bot/1.0 (+https://example.com)"}


def fetch(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def extract_first(pattern: str, text: str, flags=0, default: str | None = None) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else default


def list_1883(category_slug: str, limit: int) -> list[dict]:
    # category_slug: 'siropy' or 'pyure'
    url = f"{BASE}/catalog/produktsiya_1883_maison_routin/{category_slug}/"
    html = fetch(url)
    # find product links
    links = re.findall(r"href=\"(/catalog/produktsiya_1883_maison_routin/{}/\d+/)\"".format(category_slug), html)
    # dedupe preserve order
    seen, result = set(), []
    for href in links:
        if href in seen:
            continue
        seen.add(href)
        # try find stock near link occurrence
        idx = html.find(href)
        stock = None
        if idx != -1:
            window = html[idx: idx + 800]
            m = re.search(r"([0-9\s]+)\s*шт\.", window)
            if m:
                try:
                    stock = int(m.group(1).replace(" ", ""))
                except Exception:
                    stock = None
        result.append({"url": urljoin(BASE, href), "stock": stock})
        if len(result) >= limit:
            break
    return result


def list_tinctura(limit_per_cat: int) -> list[dict]:
    # brand page lists categories to use
    brand_url = f"{BASE}/company/brands/tinctura/"
    html = fetch(brand_url)
    cat_links = re.findall(r"href=\"(/catalog/(?:bezalkogolnye-napitki-kofe/kordial|bezalkogolnyy-alkogol)/)\"", html)
    urls = [urljoin(BASE, u) for u in dict.fromkeys(cat_links)]
    results = []
    for cu in urls:
        listing = fetch(cu)
        # collect product links
        links = re.findall(r"href=\"(/catalog/[^\"]+/\d+/)\"", listing)
        seen = set()
        for href in links:
            if href in seen:
                continue
            seen.add(href)
            full = urljoin(BASE, href)
            idx = listing.find(href)
            window = listing[max(0, idx-400): idx+800] if idx != -1 else ""
            # ensure the tile mentions Tinctura (brand or series)
            if not re.search(r"Tinctura", window, re.IGNORECASE):
                continue
            # stock near tile
            stock = None
            m = re.search(r"([0-9\s]+)\s*шт\.", window)
            if m:
                try:
                    stock = int(m.group(1).replace(" ", ""))
                except Exception:
                    stock = None
            results.append({"url": full, "stock": stock})
            # limit per specific listing path
            if sum(1 for x in results if cu in x["url"]) >= limit_per_cat:
                break
        time.sleep(0.5)
    return results


def parse_product(url: str) -> dict | None:
    html = fetch(url)
    name = extract_first(r"<meta itemprop=\"name\" content=\"([^\"]+)\"", html) or \
           extract_first(r"<span itemprop=\"name\">([^<]+)</span>", html)
    if not name:
        return None
    # price
    price = extract_first(r"itemprop=\"price\" content=\"([0-9]+(?:\.[0-9]+)?)\"", html)
    # first occurrence of vendor sku pattern `арт.XXXX`
    m = re.search(r"арт\.\s*([0-9A-Za-z/\- ]+)<", html)
    manufacturer_sku = m.group(1).strip() if m else ""
    # brand
    brand = extract_first(r">Производитель / Бренд</span>\s*<span itemprop=\"value\">\s*([^<]+)\s*<", html)
    # category type (Вид товара)
    kind = extract_first(r">Вид товара</span>\s*<span itemprop=\"value\">\s*([^<]+)\s*<", html)
    # flavor from "Характеристики"
    descr = extract_first(r">Характеристики</span>\s*<span itemprop=\"value\">\s*([^<]+)\s*<", html)
    flavor = None
    if descr:
        m2 = re.search(r"вкус:\s*([^,]+)", descr, flags=re.IGNORECASE)
        if m2:
            flavor = m2.group(1).strip()
    # volume
    volume_ml = extract_first(r">V, Объем</span>\s*<span itemprop=\"value\">\s*([0-9]+)\s*<", html)
    # composition
    composition = extract_first(r">Состав</span>\s*<span itemprop=\"value\">\s*([^<]+)\s*<", html)
    # shelf life
    shelf = extract_first(r">Срок хранения, мес</span>\s*<span itemprop=\"value\">\s*([^<]+)\s*<", html)
    # image
    image = extract_first(r"<meta property=\"og:image\" content=\"([^\"]+)\"", html)
    # fallback image link tag
    if not image:
        image = extract_first(r"<link itemprop=\"image\" href=\"([^\"]+)\"", html)

    return {
        "name": name,
        "price": float(price) if price else 0.0,
        "manufacturer_sku": manufacturer_sku,
        "brand": brand or "",
        "kind": kind or "",
        "flavor": flavor or "",
        "volume_ml": int(volume_ml) if volume_ml else None,
        "composition": composition or "",
        "shelf_life": (shelf + " мес") if shelf and not shelf.endswith("мес") else (shelf or ""),
        "image": urljoin(BASE, image) if image and image.startswith("/") else image,
    }


def upsert_product(
    data: dict,
    brand_name: str,
    parent_brand_as_category: bool,
    subcategory_name: str | None,
    stock_qty: int | None,
    sku_prefix: str = "",
    category_name: str | None = None,
) -> Product:
    brand, _ = Brand.objects.get_or_create(name=brand_name)

    # Category:
    if category_name:
        category, _ = Category.objects.get_or_create(name=category_name, parent=None)
        child_name = category.name
    else:
        # fallback: Brand as parent, kind as child
        parent_cat, _ = Category.objects.get_or_create(name=brand_name, parent=None)
        child_name = subcategory_name or data.get("kind") or "Прочее"
        category, _ = Category.objects.get_or_create(name=child_name, parent=parent_cat)

    # sku: use manufacturer sku if present else name-based
    base_sku = data.get("manufacturer_sku") or re.sub(r"\W+", "-", data["name"]).strip("-")
    sku = (sku_prefix + base_sku).strip()
    if len(sku) > 64:
        sku = sku[:64]

    product, created = Product.objects.get_or_create(
        sku=sku,
        defaults={
            "name": data["name"],
            "brand": brand,
            "category": category,
            "price": data["price"],
            "stock_qty": stock_qty or 0,
            "pack_qty": 1,
            "unit": "шт",
            "volume_ml": data.get("volume_ml"),
            "flavor": data.get("flavor", ""),
            "composition": data.get("composition", ""),
            "shelf_life": data.get("shelf_life", ""),
            "manufacturer_sku": data.get("manufacturer_sku", ""),
            "attributes": {},
        },
    )
    if not created:
        product.name = data["name"]
        product.brand = brand
        product.category = category
        product.price = data["price"]
        if stock_qty is not None:
            product.stock_qty = stock_qty
        product.volume_ml = data.get("volume_ml")
        product.flavor = data.get("flavor", "")
        product.composition = data.get("composition", "")
        product.shelf_life = data.get("shelf_life", "")
        product.manufacturer_sku = data.get("manufacturer_sku", "")
        product.save()

    # tags
    tags = []
    for t in filter(None, {child_name, brand_name, data.get("flavor", "")}):
        slug = re.sub(r"\s+", "-", t.lower())[:64]
        tag_obj, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": t})
        tags.append(tag_obj)
    if tags:
        product.tags.set(tags)

    # images (replace)
    if data.get("image"):
        product.images.all().delete()
        ProductImage.objects.create(product=product, url=data["image"], is_primary=True, ordering=0)

    return product


class Command(BaseCommand):
    help = "Scrape restinternational.ru for selected brands and categories and import into DB"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10, help="Number of items per category to import")

    def handle(self, *args, **opts):
        limit = int(opts["limit"])
        imported = 0

        # 1) 1883: siropy and pyure
        for cat in ("siropy", "pyure"):
            items = list_1883(cat, limit)
            self.stdout.write(self.style.NOTICE(f"1883/{cat}: found {len(items)} items"))
            for it in items:
                try:
                    data = parse_product(it["url"]) or {}
                    if not data:
                        continue
                    _ = upsert_product(
                        data,
                        brand_name="1883 Maison Routin",
                        parent_brand_as_category=True,
                        subcategory_name=("Сиропы" if cat == "siropy" else "Пюре"),
                        stock_qty=it.get("stock"),
                        sku_prefix="1883-",
                    )
                    imported += 1
                    time.sleep(0.5)
                except Exception as e:
                    self.stderr.write(self.style.WARNING(f"Skip {it['url']}: {e}"))

        # 2) Tinctura Anima: cordials and non-alcoholic spirits
        t_items = list_tinctura(limit)
        kept = 0
        for it in t_items:
            if kept >= limit * 2:
                break
            try:
                data = parse_product(it["url"]) or {}
                if not data:
                    continue
                # Verify brand
                if not data.get("brand", "").lower().startswith("tinctura"):
                    continue
                # Determine subcategory from URL or kind
                subcat = "Кордиалы" if "/kordial/" in it["url"] else "Безалкогольные спириты"
                _ = upsert_product(
                    data,
                    brand_name="Tinctura Anima",
                    parent_brand_as_category=True,
                    subcategory_name=subcat,
                    stock_qty=it.get("stock"),
                    sku_prefix="TINCT-",
                )
                imported += 1
                kept += 1
                time.sleep(0.5)
            except Exception as e:
                self.stderr.write(self.style.WARNING(f"Skip {it['url']}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Imported/updated: {imported}"))
