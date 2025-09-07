from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_product_extra_fields"),
        ("core", "0001_initial"),
    ]

    operations = [
        # New lookup models
        migrations.CreateModel(
            name="Color",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=80, unique=True)),
                ("hex_code", models.CharField(blank=True, max_length=7)),
            ],
        ),
        migrations.CreateModel(
            name="Country",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("iso_code", models.CharField(max_length=3, unique=True)),
            ],
        ),

        # SEO + media fields on Brand/Series/Category
        migrations.AddField(
            model_name="brand",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="brand",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="brand_photos/"),
        ),
        migrations.AddField(
            model_name="brand",
            name="meta_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="brand",
            name="meta_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="brand",
            name="meta_keywords",
            field=models.CharField(blank=True, max_length=255),
        ),

        migrations.AddField(
            model_name="series",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="series",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="series_photos/"),
        ),
        migrations.AddField(
            model_name="series",
            name="meta_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="series",
            name="meta_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="series",
            name="meta_keywords",
            field=models.CharField(blank=True, max_length=255),
        ),

        migrations.AddField(
            model_name="category",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="category_photos/"),
        ),
        migrations.AddField(
            model_name="category",
            name="meta_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="category",
            name="meta_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="category",
            name="meta_keywords",
            field=models.CharField(blank=True, max_length=255),
        ),

        # Product: SEO fields and FK conversions
        migrations.AddField(
            model_name="product",
            name="meta_title",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="product",
            name="meta_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="product",
            name="meta_keywords",
            field=models.CharField(blank=True, max_length=255),
        ),

        migrations.AlterField(
            model_name="product",
            name="sku",
            field=models.CharField(
                help_text="8-digit product code",
                max_length=8,
                unique=True,
                validators=[django.core.validators.RegexValidator(message="SKU must be exactly 8 digits.", regex="^\\d{8}$")],
            ),
        ),

        migrations.RemoveField(
            model_name="product",
            name="country_of_origin",
        ),
        migrations.RemoveField(
            model_name="product",
            name="color",
        ),
        migrations.AddField(
            model_name="product",
            name="country_of_origin",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="catalog.country"),
        ),
        migrations.AddField(
            model_name="product",
            name="color",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="catalog.color"),
        ),
    ]

