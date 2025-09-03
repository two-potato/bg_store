from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_type",
            field=models.CharField(max_length=16, choices=[("individual", "Физ. лицо"), ("company", "Юр. лицо")], default="company"),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(max_length=16, choices=[("cash", "Наличные"), ("invoice", "По счёту")], default="cash"),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_name",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_phone",
            field=models.CharField(max_length=64, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="order",
            name="address_text",
            field=models.CharField(max_length=512, null=True, blank=True),
        ),
    ]

