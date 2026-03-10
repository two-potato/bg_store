from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0010_legalentity_members_alter_sellerstore_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="sellerstore",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="sellerstore",
            name="moderation_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("approved", "Approved"), ("suspended", "Suspended")],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="sellerstore",
            name="sla_target_hours",
            field=models.PositiveIntegerField(default=24),
        ),
    ]
