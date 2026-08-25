from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0018_product_publication_status"),
        ("shopfront", "0004_alter_recentlyviewedproduct_updated_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RecommendationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("event", models.CharField(db_index=True, max_length=48)),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=64)),
                ("surface", models.CharField(blank=True, db_index=True, max_length=32)),
                ("recommendation_source", models.CharField(blank=True, db_index=True, max_length=64)),
                ("seller_id", models.IntegerField(blank=True, null=True)),
                ("brand_id", models.IntegerField(blank=True, null=True)),
                ("category_id", models.IntegerField(blank=True, null=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recommendation_events", to="catalog.product")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recommendation_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["event", "-created_at"], name="recoevent_event_created_idx"),
                    models.Index(fields=["surface", "-created_at"], name="recoevent_surface_created_idx"),
                    models.Index(fields=["recommendation_source", "-created_at"], name="recoevent_src_created_idx"),
                    models.Index(fields=["user", "-created_at"], name="recoevent_user_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationProductAffinity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("affinity_type", models.CharField(choices=[("co_purchase", "Co-purchase"), ("substitute", "Substitute"), ("similar", "Similar"), ("accessory", "Accessory")], default="co_purchase", max_length=24)),
                ("score", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("orders_count", models.PositiveIntegerField(default=0)),
                ("views_count", models.PositiveIntegerField(default=0)),
                ("source_product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outgoing_recommendation_affinities", to="catalog.product")),
                ("target_product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="incoming_recommendation_affinities", to="catalog.product")),
            ],
            options={
                "ordering": ["-score", "-orders_count", "id"],
                "indexes": [
                    models.Index(fields=["source_product", "affinity_type", "-score"], name="recoaff_src_type_score_idx"),
                    models.Index(fields=["target_product", "affinity_type", "-score"], name="recoaff_tgt_type_score_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("source_product", "target_product", "affinity_type"), name="unique_reco_affinity_edge"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationPopularitySnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("scope_type", models.CharField(choices=[("global", "Global"), ("category", "Category"), ("brand", "Brand"), ("seller", "Seller")], default="global", max_length=24)),
                ("scope_id", models.PositiveIntegerField(default=0)),
                ("window", models.CharField(default="7d", max_length=16)),
                ("score", models.DecimalField(decimal_places=4, default=0, max_digits=12)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recommendation_popularity_snapshots", to="catalog.product")),
            ],
            options={
                "ordering": ["scope_type", "scope_id", "window", "-score", "id"],
                "indexes": [
                    models.Index(fields=["scope_type", "scope_id", "window", "-score"], name="recopop_scope_score_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("scope_type", "scope_id", "window", "product"), name="unique_reco_pop_snapshot"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(db_index=True, max_length=48)),
                ("scope_type", models.CharField(choices=[("global", "Global"), ("user", "User"), ("product", "Product"), ("category", "Category"), ("brand", "Brand"), ("seller", "Seller"), ("cart", "Cart"), ("checkout", "Checkout"), ("search", "Search")], default="global", max_length=24)),
                ("scope_id", models.PositiveIntegerField(db_index=True, default=0)),
                ("source", models.CharField(blank=True, db_index=True, max_length=64)),
                ("product_ids", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
            ],
            options={
                "ordering": ["-generated_at", "-id"],
                "indexes": [
                    models.Index(fields=["kind", "scope_type", "scope_id", "-generated_at"], name="recoset_lookup_idx"),
                ],
            },
        ),
    ]
