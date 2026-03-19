from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_orderclaim"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="canceled_qty",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="sellerorderitem",
            name="canceled_qty",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
