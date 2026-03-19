from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0013_store_reviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalpolicy",
            name="required_approvals_count",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
