from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("commerce", "0002_disable_clean_noop"),
    ]

    operations = [
        migrations.AddField(
            model_name="deliveryaddress",
            name="latitude",
            field=models.DecimalField(null=True, blank=True, max_digits=9, decimal_places=6),
        ),
        migrations.AddField(
            model_name="deliveryaddress",
            name="longitude",
            field=models.DecimalField(null=True, blank=True, max_digits=9, decimal_places=6),
        ),
    ]

