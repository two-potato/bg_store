from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0012_company_workspace"),
        ("orders", "0009_wave3_seller_orders_shipments"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="approval_status",
            field=models.CharField(
                choices=[("not_required", "Approval not required"), ("pending", "Pending approval"), ("approved", "Approved"), ("rejected", "Rejected")],
                default="not_required",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="approved_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="approved_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="order",
            name="requested_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="requested_orders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name="OrderApprovalLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decision", models.CharField(choices=[("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected")], max_length=16)),
                ("comment", models.TextField(blank=True, default="")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_approval_logs", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="approval_logs", to="orders.order")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
