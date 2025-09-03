from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Brand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200)),
                (
                    "parent",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="catalog.category"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Series",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "brand",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="series", to="catalog.brand"),
                ),
            ],
            options={"unique_together": (("brand", "name"),)},
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sku", models.CharField(max_length=64, unique=True)),
                ("manufacturer_sku", models.CharField(blank=True, max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("country_of_origin", models.CharField(blank=True, max_length=120)),
                ("material", models.CharField(blank=True, max_length=120)),
                ("purpose", models.CharField(blank=True, max_length=255)),
                ("color", models.CharField(blank=True, max_length=80)),
                ("diameter_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("height_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("length_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("width_mm", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("volume_ml", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("weight_g", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("pack_qty", models.IntegerField(default=1)),
                ("unit", models.CharField(default="шт", max_length=16)),
                ("barcode", models.CharField(blank=True, max_length=64)),
                ("price", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("stock_qty", models.IntegerField(default=0)),
                ("is_new", models.BooleanField(default=False)),
                ("is_promo", models.BooleanField(default=False)),
                ("attributes", models.JSONField(blank=True, default=dict)),
                (
                    "brand",
                    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.brand"),
                ),
                (
                    "category",
                    models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.category"),
                ),
                (
                    "series",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="products", to="catalog.series"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("url", models.URLField()),
                ("alt", models.CharField(blank=True, max_length=255)),
                ("is_primary", models.BooleanField(default=False)),
                ("ordering", models.PositiveIntegerField(default=0)),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="catalog.product"),
                ),
            ],
            options={"ordering": ["ordering", "id"]},
        ),
    ]

