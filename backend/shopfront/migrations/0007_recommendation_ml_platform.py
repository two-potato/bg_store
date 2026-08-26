from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("shopfront", "0006_recommendation_aggregates"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecommendationFeatureSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("feature_set", models.CharField(choices=[("user_v1", "User v1"), ("product_v1", "Product v1"), ("global_v1", "Global v1")], db_index=True, max_length=24)),
                ("scope_type", models.CharField(choices=[("user", "User"), ("product", "Product"), ("global", "Global")], db_index=True, max_length=24)),
                ("scope_id", models.PositiveIntegerField(db_index=True, default=0)),
                ("surface", models.CharField(blank=True, db_index=True, max_length=32)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("generated_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["feature_set", "scope_type", "surface", "-generated_at", "-id"],
                "indexes": [
                    models.Index(fields=["feature_set", "scope_type", "scope_id", "surface", "-generated_at"], name="recofeat_lookup_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationTrainingDataset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("surface", models.CharField(db_index=True, max_length=32)),
                ("label_kind", models.CharField(db_index=True, default="purchase", max_length=24)),
                ("version", models.CharField(db_index=True, max_length=40)),
                ("window_start", models.DateTimeField(blank=True, null=True)),
                ("window_end", models.DateTimeField(blank=True, null=True)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("positive_count", models.PositiveIntegerField(default=0)),
                ("artifact_path", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["surface", "label_kind", "-created_at"], name="recods_surface_created_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecommendationModelArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(db_index=True, default="servio_ranker", max_length=64)),
                ("surface", models.CharField(db_index=True, max_length=32)),
                ("variant", models.CharField(db_index=True, default="ml_v1", max_length=24)),
                ("algorithm", models.CharField(default="logistic_regression", max_length=32)),
                ("version", models.CharField(db_index=True, max_length=40)),
                ("status", models.CharField(choices=[("training", "Training"), ("ready", "Ready"), ("active", "Active"), ("retired", "Retired"), ("failed", "Failed")], db_index=True, default="training", max_length=16)),
                ("feature_names", models.JSONField(blank=True, default=list)),
                ("intercept", models.FloatField(default=0.0)),
                ("weights", models.JSONField(blank=True, default=dict)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("artifact_path", models.CharField(blank=True, max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("activated_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("trained_on", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="models", to="shopfront.recommendationtrainingdataset")),
            ],
            options={
                "ordering": ["surface", "variant", "-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["surface", "variant", "status", "-created_at"], name="recomodel_surface_idx"),
                ],
            },
        ),
    ]
