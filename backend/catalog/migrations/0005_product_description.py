from django.db import migrations, models


def _build_two_paragraphs(product):
    name = (getattr(product, "name", "") or "Товар").strip()
    brand_name = (getattr(getattr(product, "brand", None), "name", "") or "бренда Bad Guys").strip()
    category_name = (getattr(getattr(product, "category", None), "name", "") or "категории магазина").strip()
    flavor = (getattr(product, "flavor", "") or "").strip()
    unit = (getattr(product, "unit", "") or "шт").strip()
    composition = (getattr(product, "composition", "") or "").strip()
    shelf_life = (getattr(product, "shelf_life", "") or "").strip()

    p1 = (
        f"{name} от {brand_name} — позиция из раздела «{category_name}», "
        "подготовленная для стабильного ежедневного использования в баре, кофейне и дома. "
        f"Товар поставляется в удобной фасовке ({unit}), легко встраивается в рабочие процессы "
        "и подходит для регулярного пополнения ассортимента."
    )

    details = []
    if flavor:
        details.append(f"вкус: {flavor}")
    if composition:
        details.append(f"состав: {composition}")
    if shelf_life:
        details.append(f"срок годности: {shelf_life}")
    details_text = "; ".join(details) if details else "базовые характеристики: сбалансированный профиль и предсказуемый результат"

    p2 = (
        "Описание товара для клиента: "
        f"{details_text}. "
        "Рекомендуем хранить продукт в сухом месте при комнатной температуре и использовать в рамках "
        "стандартных технологических карт, чтобы сохранять качество напитков и стабильность вкуса."
    )
    return f"{p1}\n\n{p2}"


def fill_product_descriptions(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    for product in Product.objects.select_related("brand", "category").all().iterator():
        if (product.description or "").strip():
            continue
        product.description = _build_two_paragraphs(product)
        product.save(update_fields=["description"])


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_ref_updates"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(fill_product_descriptions, migrations.RunPython.noop),
    ]

