from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_wave3_marketplace_systemization"),
        ("orders", "0008_guest_checkout_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="seller_offer",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="catalog.selleroffer"),
        ),
        migrations.CreateModel(
            name="SellerOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("seller_store_name", models.CharField(blank=True, default="", max_length=255)),
                ("status", models.CharField(choices=[("new", "New"), ("accepted", "Accepted"), ("picking", "Picking"), ("shipped", "Shipped"), ("delivered", "Delivered"), ("canceled", "Canceled")], default="new", max_length=16)),
                ("customer_comment", models.TextField(blank=True, default="")),
                ("internal_comment", models.TextField(blank=True, default="")),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("shipped_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seller_orders", to="orders.order")),
                ("seller", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="seller_orders", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SellerOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("qty", models.PositiveIntegerField(default=1)),
                ("order_item", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="seller_order_item", to="orders.orderitem")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product")),
                ("seller_offer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="seller_order_items", to="catalog.selleroffer")),
                ("seller_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.sellerorder")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Shipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tracking_number", models.CharField(blank=True, default="", max_length=120)),
                ("delivery_method", models.CharField(blank=True, default="", max_length=120)),
                ("warehouse_name", models.CharField(blank=True, default="", max_length=120)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready"), ("in_transit", "In transit"), ("delivered", "Delivered"), ("issue", "Issue")], default="draft", max_length=16)),
                ("packed_at", models.DateTimeField(blank=True, null=True)),
                ("shipped_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("seller_order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipments", to="orders.sellerorder")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ShipmentItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("qty", models.PositiveIntegerField(default=1)),
                ("seller_order_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="shipment_items", to="orders.sellerorderitem")),
                ("shipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.shipment")),
            ],
        ),
        migrations.AddConstraint(
            model_name="sellerorder",
            constraint=models.UniqueConstraint(fields=("order", "seller"), name="unique_seller_order_per_order"),
        ),
        migrations.AddIndex(
            model_name="sellerorder",
            index=models.Index(fields=["seller", "status", "-created_at"], name="sellerorder_status_idx"),
        ),
        migrations.AddIndex(
            model_name="shipment",
            index=models.Index(fields=["status", "-created_at"], name="shipment_status_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="shipmentitem",
            constraint=models.UniqueConstraint(fields=("shipment", "seller_order_item"), name="unique_shipment_seller_order_item"),
        ),
    ]
