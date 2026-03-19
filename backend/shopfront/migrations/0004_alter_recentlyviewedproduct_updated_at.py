from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("shopfront", "0003_growth_lists_and_recent_views"),
    ]

    operations = [
        migrations.AlterField(
            model_name="recentlyviewedproduct",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
