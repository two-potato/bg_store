from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="IdempotencyKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_id", models.IntegerField()),
                ("route", models.CharField(max_length=255)),
                ("key", models.CharField(max_length=64)),
                ("response", models.JSONField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
            ],
            options={
                "unique_together": (("user_id", "route", "key"),),
            },
        ),
    ]

