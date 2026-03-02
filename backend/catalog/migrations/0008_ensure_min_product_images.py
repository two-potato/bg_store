from django.db import migrations


def ensure_min_images(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    ProductImage = apps.get_model("catalog", "ProductImage")

    for product in Product.objects.all().iterator():
        current = ProductImage.objects.filter(product_id=product.id).count()
        if current >= 3:
            continue
        for idx in range(current, 3):
            ProductImage.objects.create(
                product_id=product.id,
                url=f"https://picsum.photos/seed/p-{product.id}-{idx + 1}/600/400",
                alt=product.name,
                is_primary=(idx == 0 and current == 0),
                ordering=idx,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_productreviewcomment"),
    ]

    operations = [
        migrations.RunPython(ensure_min_images, migrations.RunPython.noop),
    ]
