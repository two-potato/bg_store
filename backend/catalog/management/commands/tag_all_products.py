from django.core.management.base import BaseCommand
from django.utils.text import slugify
from catalog.models import Product, Tag


class Command(BaseCommand):
    help = "Ensure every product has tags: brand, category, and flags (Новинка/Акция)."

    def handle(self, *args, **options):
        created_tags = 0
        attached = 0
        for p in Product.objects.select_related("brand", "category").all():
            tags = []
            if p.brand:
                tags.append((p.brand.name, f"brand-{slugify(p.brand.name)}"))
            if p.category:
                tags.append((p.category.name, f"cat-{slugify(p.category.name)}"))
            if p.is_new:
                tags.append(("Новинка", "flag-new"))
            if p.is_promo:
                tags.append(("Акция", "flag-promo"))
            # Fallback: ensure at least one tag tied to SKU prefix
            if not tags:
                parts = (p.sku or "").split("-")
                if parts:
                    tags.append((parts[0], f"sku-{slugify(parts[0])}"))
            for name, slug in tags:
                tag, was_created = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
                if was_created:
                    created_tags += 1
                if not p.tags.filter(id=tag.id).exists():
                    p.tags.add(tag)
                    attached += 1
        self.stdout.write(self.style.SUCCESS(
            f"Tags created: {created_tags}; attachments made: {attached}"
        ))

