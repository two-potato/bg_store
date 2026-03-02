from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_friendship_and_profile_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="role",
            field=models.CharField(choices=[("admin", "Админ"), ("manager", "Менеджер"), ("client", "Клиент")], default="client", max_length=16),
        ),
    ]

