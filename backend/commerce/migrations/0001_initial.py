from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from commerce.validators import validate_inn, validate_bik


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LegalEntity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("inn", models.CharField(max_length=12, unique=True, validators=[validate_inn])),
                ("bik", models.CharField(max_length=9, validators=[validate_bik])),
                ("checking_account", models.CharField(max_length=20)),
                ("bank_name", models.CharField(blank=True, max_length=255, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="LegalEntityMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "role",
                    models.CharField(
                        choices=[("owner", "Владелец"), ("admin", "Админ"), ("manager", "Менеджер"), ("viewer", "Наблюдатель")],
                        default="manager",
                        max_length=16,
                    ),
                ),
                ("legal_entity", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="commerce.legalentity")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": (("user", "legal_entity"),)},
        ),
        migrations.CreateModel(
            name="DeliveryAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("label", models.CharField(max_length=255)),
                ("country", models.CharField(max_length=128)),
                ("city", models.CharField(max_length=128)),
                ("street", models.CharField(max_length=255)),
                ("postcode", models.CharField(max_length=32)),
                ("details", models.CharField(blank=True, max_length=255, null=True)),
                ("is_default", models.BooleanField(default=False)),
                (
                    "legal_entity",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delivery_addresses", to="commerce.legalentity"),
                ),
            ],
            options={"unique_together": (("legal_entity", "label"),)},
        ),
        migrations.CreateModel(
            name="MembershipRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("comment", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "На рассмотрении"), ("approved", "Одобрено"), ("rejected", "Отклонено")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "applicant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="membership_requests", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "legal_entity",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="membership_requests", to="commerce.legalentity"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LegalEntityCreationRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("inn", models.CharField(max_length=12, validators=[validate_inn])),
                ("bik", models.CharField(max_length=9, validators=[validate_bik])),
                ("checking_account", models.CharField(max_length=20)),
                ("bank_name", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "На рассмотрении"), ("approved", "Одобрено"), ("rejected", "Отклонено")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                (
                    "applicant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entity_creation_requests", to=settings.AUTH_USER_MODEL),
                ),
            ],
        ),
    ]

