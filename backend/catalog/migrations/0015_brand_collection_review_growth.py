from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def fill_brand_slugs(apps, schema_editor):
    Brand = apps.get_model("catalog", "Brand")
    for brand in Brand.objects.all().iterator():
        if brand.slug:
            continue
        base = slugify(brand.name) or f"brand-{brand.pk}"
        candidate = base
        suffix = 2
        while Brand.objects.filter(slug=candidate).exclude(pk=brand.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        brand.slug = candidate
        brand.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_product_documents_and_commercial_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="brand",
            name="slug",
            field=models.SlugField(blank=True, null=True, max_length=160, unique=True, db_index=False),
        ),
        migrations.RunPython(fill_brand_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="brand",
            name="slug",
            field=models.SlugField(blank=True, max_length=160, unique=True, db_index=False),
        ),
        migrations.AddField(
            model_name="productreview",
            name="helpful_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="productreview",
            name="is_verified_purchase",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="productreview",
            name="unhelpful_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="Collection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("meta_title", models.CharField(blank=True, max_length=255)),
                ("meta_description", models.TextField(blank=True)),
                ("meta_keywords", models.CharField(blank=True, max_length=255)),
                ("name", models.CharField(max_length=160, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=180, unique=True, db_index=False)),
                ("description", models.TextField(blank=True)),
                ("photo", models.ImageField(blank=True, null=True, upload_to="collection_photos/")),
                ("hero_title", models.CharField(blank=True, max_length=200)),
                ("hero_text", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_featured", models.BooleanField(default=False)),
            ],
            options={"ordering": ["-is_featured", "name"]},
        ),
        migrations.CreateModel(
            name="ProductQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("question_text", models.TextField()),
                ("answer_text", models.TextField(blank=True, default="")),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("is_public", models.BooleanField(default=True)),
                ("answered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="answered_product_questions", to=settings.AUTH_USER_MODEL)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="catalog.product")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_questions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ProductReviewPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("image_url", models.URLField()),
                ("caption", models.CharField(blank=True, max_length=160)),
                ("ordering", models.PositiveIntegerField(default=0)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="catalog.productreview")),
            ],
            options={"ordering": ["ordering", "id"]},
        ),
        migrations.CreateModel(
            name="CollectionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ordering", models.PositiveIntegerField(default=0)),
                ("highlight", models.CharField(blank=True, max_length=120)),
                ("collection", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="catalog.collection")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="collection_items", to="catalog.product")),
            ],
            options={"ordering": ["ordering", "id"]},
        ),
        migrations.AddField(
            model_name="collection",
            name="products",
            field=models.ManyToManyField(blank=True, related_name="collections", through="catalog.CollectionItem", to="catalog.product"),
        ),
        migrations.CreateModel(
            name="ProductReviewVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("value", models.CharField(choices=[("helpful", "Helpful"), ("unhelpful", "Unhelpful")], max_length=16)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="votes", to="catalog.productreview")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_review_votes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="collectionitem",
            constraint=models.UniqueConstraint(fields=("collection", "product"), name="unique_collection_product"),
        ),
        migrations.AddConstraint(
            model_name="productreviewvote",
            constraint=models.UniqueConstraint(fields=("review", "user"), name="unique_review_vote_per_user"),
        ),
    ]
