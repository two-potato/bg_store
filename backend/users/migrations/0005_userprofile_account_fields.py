from django.db import migrations, models


def backfill_profiles(apps, schema_editor):
    User = apps.get_model("users", "User")
    UserProfile = apps.get_model("users", "UserProfile")

    existing_profile_user_ids = set(UserProfile.objects.values_list("user_id", flat=True))
    to_create = []
    for user in User.objects.all().iterator():
        if user.id in existing_profile_user_ids:
            continue
        to_create.append(
            UserProfile(
                user_id=user.id,
                full_name=(f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}").strip() or (user.username or ""),
                contact_email=(user.email or "").strip(),
            )
        )
    if to_create:
        UserProfile.objects.bulk_create(to_create, batch_size=500)

    for profile in UserProfile.objects.select_related("user").all().iterator():
        if not profile.full_name:
            profile.full_name = (
                f"{(profile.user.first_name or '').strip()} {(profile.user.last_name or '').strip()}"
            ).strip() or (profile.user.username or "")
        if not profile.contact_email:
            profile.contact_email = (profile.user.email or "").strip()
        profile.save(update_fields=["full_name", "contact_email"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_userprofile_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="contact_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="full_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RunPython(backfill_profiles, migrations.RunPython.noop),
    ]
