import json
from django.core.management.base import BaseCommand, CommandError
from catalog.models import Brand, Category, Product, ProductImage, Tag


class Command(BaseCommand):
    help = "Import products from a JSON file with explicit fields."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to JSON file")

    def handle(self, *args, **opts):
        path = opts["path"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise CommandError(f"Failed to read JSON: {e}")

        if not isinstance(data, list):
            raise CommandError("Root JSON must be a list of products")

        created, updated = 0, 0

        for item in data:
            try:
                brand_name = item.get("brand")
                category_name = item.get("category")
                subcategory_name = item.get("subcategory")
                sku = item.get("sku")
                name = item.get("name")
                price = item.get("price", 0)
                stock_qty = int(item.get("stock_qty", 0))
                pack_qty = int(item.get("pack_qty", 1))
                unit = item.get("unit", "шт")
                volume_ml = item.get("volume_ml")
                flavor = item.get("flavor", "")
                composition = item.get("composition", "")
                shelf_life = item.get("shelf_life", "")
                manufacturer_sku = item.get("manufacturer_sku", "")
                barcode = item.get("barcode", "")
                description = item.get("description", "")
                image = item.get("image")
                images = item.get("images") or ([image] if image else [])
                tags = item.get("tags", [])

                if not (brand_name and category_name and sku and name):
                    self.stderr.write(self.style.WARNING(f"Skip: missing required fields for SKU {sku!r}"))
                    continue

                brand, _ = Brand.objects.get_or_create(name=brand_name)

                parent_cat, _ = Category.objects.get_or_create(name=category_name, parent=None)
                if subcategory_name:
                    category, _ = Category.objects.get_or_create(name=subcategory_name, parent=parent_cat)
                else:
                    category = parent_cat

                product, was_created = Product.objects.get_or_create(
                    sku=sku,
                    defaults={
                        "name": name,
                        "brand": brand,
                        "category": category,
                        "price": price,
                        "stock_qty": stock_qty,
                        "pack_qty": pack_qty,
                        "unit": unit,
                        "volume_ml": volume_ml or None,
                        "flavor": flavor,
                        "composition": composition,
                        "shelf_life": shelf_life,
                        "manufacturer_sku": manufacturer_sku,
                        "barcode": barcode,
                        "attributes": {"description": description} if description else {},
                    },
                )
                if not was_created:
                    # update fields
                    product.name = name
                    product.brand = brand
                    product.category = category
                    product.price = price
                    product.stock_qty = stock_qty
                    product.pack_qty = pack_qty
                    product.unit = unit
                    product.volume_ml = volume_ml or None
                    product.flavor = flavor
                    product.composition = composition
                    product.shelf_life = shelf_life
                    product.manufacturer_sku = manufacturer_sku
                    product.barcode = barcode
                    if description:
                        product.attributes = {**(product.attributes or {}), "description": description}
                    product.save()

                # tags
                tag_objs = []
                for t in tags:
                    slug = str(t).lower().replace(" ", "-")[:64]
                    tag_obj, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": t})
                    tag_objs.append(tag_obj)
                if tag_objs:
                    product.tags.set(tag_objs)

                # images (replace order)
                if images:
                    product.images.all().delete()
                    for idx, img_url in enumerate(images):
                        if not img_url:
                            continue
                        ProductImage.objects.create(product=product, url=img_url, is_primary=(idx == 0), ordering=idx)

                created += 1 if was_created else 0
                updated += 0 if was_created else 1

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error importing {item.get('sku','?')}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Imported: created={created}, updated={updated}"))

