from django.db import migrations
from django.utils.text import slugify


def ensure_min_tags(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    Tag = apps.get_model("catalog", "Tag")

    for product in Product.objects.select_related("brand", "category", "country_of_origin").all().iterator():
        tag_candidates = []

        if product.brand_id and product.brand and product.brand.name:
            tag_candidates.append((product.brand.name, f"brand-{slugify(product.brand.name)}"))
        if product.category_id and product.category and product.category.name:
            tag_candidates.append((product.category.name, f"cat-{slugify(product.category.name)}"))
        if product.country_of_origin_id and product.country_of_origin and product.country_of_origin.name:
            tag_candidates.append((product.country_of_origin.name, f"country-{slugify(product.country_of_origin.name)}"))
        if product.is_new:
            tag_candidates.append(("Новинка", "flag-new"))
        if product.is_promo:
            tag_candidates.append(("Акция", "flag-promo"))
        if product.flavor:
            tag_candidates.append((product.flavor, f"flavor-{slugify(product.flavor)}"))

        sku_prefix = (product.sku or "")[:2] or "00"
        tag_candidates.extend([
            ("Товар", "type-product"),
            ("Каталог", "type-catalog"),
            ("Ассортимент", "type-assortment"),
            (f"SKU {sku_prefix}", f"sku-prefix-{slugify(sku_prefix)}"),
        ])

        for name, slug in tag_candidates:
            if product.tags.count() >= 4:
                break
            tag, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
            if not product.tags.filter(id=tag.id).exists():
                product.tags.add(tag)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0008_ensure_min_product_images"),
    ]

    operations = [
        migrations.RunPython(ensure_min_tags, migrations.RunPython.noop),
    ]

