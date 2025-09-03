from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django_fsm


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0001_initial"),
        ("catalog", "0001_initial"),
        ("commerce", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", django_fsm.FSMField(default="new", max_length=50, protected=True)),
                ("subtotal", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                ("discount_amount", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                (
                    "delivery_address",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="commerce.deliveryaddress"),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="commerce.legalentity"),
                ),
                (
                    "placed_by",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="placed_orders", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("qty", models.PositiveIntegerField(default=1)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order"),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="catalog.product"),
                ),
            ],
        ),
    ]

