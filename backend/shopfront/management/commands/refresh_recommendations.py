from django.core.management.base import BaseCommand

from shopfront.tasks import (
    refresh_recommendation_affinities,
    refresh_recommendation_ml_features,
    refresh_recommendation_popularity,
    refresh_recommendation_replenishment,
    refresh_recommendation_sets,
    refresh_recommendation_user_affinity,
)


class Command(BaseCommand):
    help = "Refresh recommendation popularity, affinities, user affinity, replenishment, and materialized recommendation sets."

    def add_arguments(self, parser):
        parser.add_argument("--window", default="7d", help="Popularity window, for example 7d or 30d.")
        parser.add_argument("--limit", type=int, default=60, help="Snapshot limit per scope.")
        parser.add_argument("--set-limit", type=int, default=8, help="Recommendation set size.")

    def handle(self, *args, **options):
        window = str(options["window"] or "7d")
        limit = int(options["limit"] or 60)
        set_limit = int(options["set_limit"] or 8)
        pop_count = refresh_recommendation_popularity(window=window, limit=limit)
        affinity_count = refresh_recommendation_affinities()
        user_affinity_count = refresh_recommendation_user_affinity()
        replenishment_count = refresh_recommendation_replenishment()
        feature_result = refresh_recommendation_ml_features()
        set_result = refresh_recommendation_sets(limit=set_limit)
        self.stdout.write(
            self.style.SUCCESS(
                "recommendations refreshed: "
                f"popularity={pop_count}, affinities={affinity_count}, "
                f"user_affinity={user_affinity_count}, replenishment={replenishment_count}, features={feature_result}, sets={set_result}"
            )
        )
