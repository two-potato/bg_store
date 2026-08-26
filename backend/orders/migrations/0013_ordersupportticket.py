from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_partial_fulfillment_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderSupportTicket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("topic", models.CharField(choices=[("support", "Поддержка"), ("payment", "Платёж"), ("delivery", "Доставка"), ("documents", "Документы")], default="support", max_length=24)),
                ("status", models.CharField(choices=[("open", "Открыт"), ("in_progress", "В работе"), ("resolved", "Решён"), ("closed", "Закрыт")], default="open", max_length=24)),
                ("subject", models.CharField(max_length=255)),
                ("message", models.TextField()),
                ("resolution_comment", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_support_tickets", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_tickets", to="orders.order")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="ordersupportticket",
            index=models.Index(fields=["status", "-created_at"], name="ordersupport_status_idx"),
        ),
    ]
