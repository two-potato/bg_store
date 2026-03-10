from django import template

register = template.Library()


@register.filter(name="product_image_alt")
def product_image_alt(image, fallback_name: str = ""):
    alt = ((getattr(image, "alt", "") or "") if image is not None else "").strip()
    if not alt or alt.lower().startswith("load product"):
        return (fallback_name or "Изображение товара").strip()
    return alt
