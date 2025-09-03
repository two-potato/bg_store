from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_add_checkout_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="delivery_address",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="commerce.deliveryaddress"),
        ),
        migrations.AlterField(
            model_name="order",
            name="legal_entity",
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="commerce.legalentity"),
        ),
    ]

