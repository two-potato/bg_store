from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commerce", "0012_company_workspace"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("rating", models.PositiveSmallIntegerField()),
                ("text", models.TextField(blank=True, default="")),
                ("is_verified_buyer", models.BooleanField(default=False)),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="commerce.sellerstore")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="store_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="storereview",
            constraint=models.UniqueConstraint(fields=("store", "user"), name="unique_store_review_per_user"),
        ),
    ]
