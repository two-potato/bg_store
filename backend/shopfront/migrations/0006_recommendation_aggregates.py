from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0018_product_publication_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("shopfront", "0005_recommendation_foundations"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecommendationUserAffinity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("dimension", models.CharField(choices=[("brand", "Brand"), ("category", "Category"), ("seller", "Seller"), ("tag", "Tag"), ("price_band", "Price band")], db_index=True, max_length=24)),
                ("entity_id", models.PositiveIntegerField(db_index=True, default=0)),
                ("entity_key", models.CharField(blank=True, db_index=True, max_length=64)),
                ("score", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("event_count", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_affinities", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["user_id", "dimension", "-score", "id"],
                "indexes": [
                    models.Index(fields=["user", "dimension", "-score"], name="recouseraff_user_dim_idx"),
                    models.Index(fields=["dimension", "entity_id", "-score"], name="recouseraff_dim_entity_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "dimension", "entity_id", "entity_key"), name="unique_reco_user_affinity"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationReplenishmentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("first_ordered_at", models.DateTimeField(blank=True, null=True)),
                ("last_ordered_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("orders_count", models.PositiveIntegerField(default=0)),
                ("quantity_total", models.PositiveIntegerField(default=0)),
                ("expected_interval_days", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("score", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_replenishment_profiles", to="catalog.product")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_replenishment_profiles", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["user_id", "-score", "-last_ordered_at", "id"],
                "indexes": [
                    models.Index(fields=["user", "-score", "-last_ordered_at"], name="recoreplen_user_score_idx"),
                    models.Index(fields=["product", "-score"], name="recoreplen_product_score_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "product"), name="unique_reco_replenishment_profile"),
                ],
            },
        ),
    ]
