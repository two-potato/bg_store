from django.db import migrations
from django.utils.text import slugify


def normalize_slugs(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")

    for c in Category.objects.all().iterator():
        slug = (c.slug or "").strip()
        if slug and not slug.isdigit():
            continue
        base = slugify(c.name)
        if not base or base.isdigit():
            base = f"category-{c.pk}"
        candidate = base
        suffix = 2
        while Category.objects.filter(slug=candidate).exclude(pk=c.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        c.slug = candidate
        c.save(update_fields=["slug"])

    for p in Product.objects.all().iterator():
        slug = (p.slug or "").strip()
        if slug and not slug.isdigit():
            continue
        base = slugify(p.name)
        if not base or base.isdigit():
            base = f"product-{p.pk}"
        candidate = base
        suffix = 2
        while Product.objects.filter(slug=candidate).exclude(pk=p.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        p.slug = candidate
        p.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0010_add_slugs_for_category_and_product"),
    ]

    operations = [
        migrations.RunPython(normalize_slugs, migrations.RunPython.noop),
    ]
