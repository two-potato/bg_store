from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_profile_phone"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="user_photos/"),
        ),
        migrations.CreateModel(
            name="Friendship",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("accepted", models.BooleanField(default=False)),
                (
                    "from_user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_initiated", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "to_user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="friendships_received", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"unique_together": (("from_user", "to_user"),)},
        ),
    ]

