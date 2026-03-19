from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0011_sellerstore_ops_fields"),
        ("catalog", "0015_brand_collection_review_growth"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="faq_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="brand",
            name="faq_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="brand",
            name="landing_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="faq_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="faq_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="category",
            name="hero_text",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="hero_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="category",
            name="landing_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="collection",
            name="faq_body",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="collection",
            name="faq_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="collection",
            name="landing_body",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="SellerOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("offer_title", models.CharField(blank=True, max_length=255)),
                ("price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("min_order_qty", models.PositiveIntegerField(default=1)),
                ("lead_time_days", models.PositiveIntegerField(default=0)),
                ("status", models.CharField(choices=[("active", "Active"), ("paused", "Paused"), ("out_of_stock", "Out of stock"), ("archived", "Archived")], default="active", max_length=16)),
                ("is_featured", models.BooleanField(default=False)),
                ("warehouse_source", models.CharField(blank=True, max_length=120)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seller_offers", to="catalog.product")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seller_offers", to=settings.AUTH_USER_MODEL)),
                ("seller_store", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="offers", to="commerce.sellerstore")),
            ],
            options={
                "ordering": ["-is_featured", "price", "id"],
            },
        ),
        migrations.CreateModel(
            name="SellerInventory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("warehouse_name", models.CharField(max_length=120)),
                ("warehouse_code", models.CharField(blank=True, max_length=64)),
                ("stock_qty", models.IntegerField(default=0)),
                ("reserved_qty", models.IntegerField(default=0)),
                ("incoming_qty", models.IntegerField(default=0)),
                ("eta_days", models.PositiveIntegerField(default=0)),
                ("is_primary", models.BooleanField(default=False)),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventories", to="catalog.selleroffer")),
            ],
            options={
                "ordering": ["-is_primary", "warehouse_name", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="selleroffer",
            constraint=models.UniqueConstraint(fields=("product", "seller"), name="unique_product_seller_offer"),
        ),
        migrations.AddIndex(
            model_name="selleroffer",
            index=models.Index(fields=["product", "status", "price"], name="selleroffer_prod_price_idx"),
        ),
        migrations.AddIndex(
            model_name="selleroffer",
            index=models.Index(fields=["seller", "status", "price"], name="selleroffer_seller_price_idx"),
        ),
        migrations.AddConstraint(
            model_name="sellerinventory",
            constraint=models.UniqueConstraint(fields=("offer", "warehouse_name"), name="unique_offer_warehouse_name"),
        ),
        migrations.AddIndex(
            model_name="sellerinventory",
            index=models.Index(fields=["offer", "-is_primary"], name="sellerinv_offer_primary_idx"),
        ),
    ]
