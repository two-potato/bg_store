from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0011_sellerstore_ops_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("display_name", models.CharField(blank=True, default="", max_length=255)),
                ("procurement_email", models.EmailField(blank=True, default="", max_length=254)),
                ("is_active", models.BooleanField(default=True)),
                ("legal_entity", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="company", to="commerce.legalentity")),
            ],
            options={"verbose_name": "Компания", "verbose_name_plural": "Компании"},
        ),
        migrations.CreateModel(
            name="ApprovalPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_enabled", models.BooleanField(default=False)),
                ("auto_approve_below", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("require_approver_role", models.BooleanField(default=True)),
                ("require_comment", models.BooleanField(default=False)),
                ("max_pending_hours", models.PositiveIntegerField(default=24)),
                ("company", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="approval_policy", to="commerce.company")),
            ],
            options={"verbose_name": "Политика согласования", "verbose_name_plural": "Политики согласования"},
        ),
        migrations.CreateModel(
            name="CompanyMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Admin"), ("buyer", "Buyer"), ("approver", "Approver"), ("finance", "Finance")], default="buyer", max_length=16)),
                ("approval_limit", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("is_default_approver", models.BooleanField(default=False)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="commerce.company")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="company_memberships", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="companymembership",
            constraint=models.UniqueConstraint(fields=("user", "company"), name="unique_user_company_membership"),
        ),
    ]
