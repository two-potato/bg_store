from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_add_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="flavor",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="product",
            name="composition",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="product",
            name="shelf_life",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]

