from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")

    # Categories
    used = set()
    for c in Category.objects.all().iterator():
        base = slugify(c.name)
        if not base or base.isdigit():
            base = f"category-{c.pk}"
        candidate = base
        suffix = 2
        while candidate in used or Category.objects.filter(slug=candidate).exclude(pk=c.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        c.slug = candidate
        c.save(update_fields=["slug"])
        used.add(candidate)

    # Products
    used = set()
    for p in Product.objects.all().iterator():
        base = slugify(p.name)
        if not base or base.isdigit():
            base = f"product-{p.pk}"
        candidate = base
        suffix = 2
        while candidate in used or Product.objects.filter(slug=candidate).exclude(pk=p.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        p.slug = candidate
        p.save(update_fields=["slug"])
        used.add(candidate)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0009_ensure_min_product_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="slug",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="slug",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE catalog_category ALTER COLUMN slug SET DEFAULT '';"
                "ALTER TABLE catalog_category ALTER COLUMN slug SET NOT NULL;"
                "ALTER TABLE catalog_category ALTER COLUMN slug DROP DEFAULT;"
            ),
            reverse_sql=(
                "ALTER TABLE catalog_category ALTER COLUMN slug DROP NOT NULL;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE catalog_product ALTER COLUMN slug SET DEFAULT '';"
                "ALTER TABLE catalog_product ALTER COLUMN slug SET NOT NULL;"
                "ALTER TABLE catalog_product ALTER COLUMN slug DROP DEFAULT;"
            ),
            reverse_sql=(
                "ALTER TABLE catalog_product ALTER COLUMN slug DROP NOT NULL;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'catalog_category_slug_dbf63ad0_uniq') THEN "
                "ALTER TABLE catalog_category ADD CONSTRAINT catalog_category_slug_dbf63ad0_uniq UNIQUE (slug); "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "ALTER TABLE catalog_category DROP CONSTRAINT IF EXISTS catalog_category_slug_dbf63ad0_uniq;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ "
                "BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'catalog_product_slug_f37848b0_uniq') THEN "
                "ALTER TABLE catalog_product ADD CONSTRAINT catalog_product_slug_f37848b0_uniq UNIQUE (slug); "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "ALTER TABLE catalog_product DROP CONSTRAINT IF EXISTS catalog_product_slug_f37848b0_uniq;"
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="category",
                    name="slug",
                    field=models.SlugField(blank=True, db_index=False, max_length=255, unique=True),
                ),
                migrations.AlterField(
                    model_name="product",
                    name="slug",
                    field=models.SlugField(blank=True, db_index=False, max_length=255, unique=True),
                ),
            ],
        ),
    ]
