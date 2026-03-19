from django.core.management.base import BaseCommand

from shopfront.recommendation_feature_store import refresh_recommendation_feature_snapshots


class Command(BaseCommand):
    help = "Refresh recommendation ML feature snapshots for users and products."

    def add_arguments(self, parser):
        parser.add_argument("--user-limit", type=int, default=1000)
        parser.add_argument("--product-limit", type=int, default=2000)

    def handle(self, *args, **options):
        result = refresh_recommendation_feature_snapshots(
            user_limit=int(options["user_limit"] or 1000),
            product_limit=int(options["product_limit"] or 2000),
        )
        self.stdout.write(self.style.SUCCESS(f"recommendation feature snapshots refreshed: {result}"))
