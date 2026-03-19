from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_company_approval_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("claim_type", models.CharField(choices=[("return", "Возврат"), ("damage", "Повреждение"), ("shortage", "Недовложение"), ("delivery", "Проблема доставки"), ("other", "Другое")], default="other", max_length=24)),
                ("status", models.CharField(choices=[("open", "Открыто"), ("in_review", "На рассмотрении"), ("resolved", "Решено"), ("rejected", "Отклонено")], default="open", max_length=24)),
                ("message", models.TextField()),
                ("resolution_comment", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_claims", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="claims", to="orders.order")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="orderclaim",
            index=models.Index(fields=["status", "-created_at"], name="orderclaim_status_created_idx"),
        ),
    ]
