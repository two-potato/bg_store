from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0013_ordersupportticket"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="delivery_method",
            field=models.CharField(
                choices=[("courier", "Курьер"), ("pickup", "Самовывоз")],
                default="courier",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="pickup_point",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
