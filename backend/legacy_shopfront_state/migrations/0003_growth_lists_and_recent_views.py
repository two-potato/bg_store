from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("shopfront", "0002_persistentcart_categorysubscription_brandsubscription"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0015_brand_collection_review_growth"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecentlyViewedProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recently_viewed_by", to="catalog.product")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recently_viewed_products", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="SavedList",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=140)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("share_token", models.CharField(blank=True, db_index=True, max_length=40, unique=True)),
                ("is_public", models.BooleanField(default=False)),
                ("source", models.CharField(choices=[("manual", "Manual"), ("favorites", "Favorites"), ("order", "Order"), ("cart", "Cart")], default="manual", max_length=24)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_lists", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SavedListItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("note", models.CharField(blank=True, max_length=180)),
                ("ordering", models.PositiveIntegerField(default=0)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="saved_list_items", to="catalog.product")),
                ("saved_list", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="shopfront.savedlist")),
            ],
            options={"ordering": ["ordering", "-updated_at", "id"]},
        ),
        migrations.AddIndex(
            model_name="recentlyviewedproduct",
            index=models.Index(fields=["user", "-updated_at"], name="recent_view_user_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="savedlist",
            index=models.Index(fields=["user", "-updated_at"], name="saved_list_user_updated_idx"),
        ),
        migrations.AddConstraint(
            model_name="recentlyviewedproduct",
            constraint=models.UniqueConstraint(fields=("user", "product"), name="unique_recently_viewed_product_per_user"),
        ),
        migrations.AddConstraint(
            model_name="savedlistitem",
            constraint=models.UniqueConstraint(fields=("saved_list", "product"), name="unique_saved_list_product"),
        ),
    ]
