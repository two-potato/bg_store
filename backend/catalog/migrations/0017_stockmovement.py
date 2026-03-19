import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_wave3_marketplace_systemization"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("field_type", models.CharField(choices=[("stock", "Остаток"), ("reserved", "Резерв"), ("incoming", "В пути")], max_length=16)),
                ("delta", models.IntegerField()),
                ("before_value", models.IntegerField(default=0)),
                ("after_value", models.IntegerField(default=0)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to=settings.AUTH_USER_MODEL)),
                ("inventory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="catalog.sellerinventory")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["inventory", "-created_at"], name="stockmv_inv_created_idx"),
        ),
    ]
