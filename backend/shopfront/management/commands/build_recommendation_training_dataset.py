from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from shopfront.recommendation.ml import build_training_dataset


class Command(BaseCommand):
    help = "Build an offline recommendation training dataset from recommendation exposure logs."

    def add_arguments(self, parser):
        parser.add_argument("--surface", default="home")
        parser.add_argument("--label-kind", default="purchase")
        parser.add_argument("--window-days", type=int, default=int(getattr(settings, "RECOMMENDATION_ML_TRAINING_WINDOW_DAYS", 30)))

    def handle(self, *args, **options):
        until = timezone.now()
        since = until - timedelta(days=int(options["window_days"] or 30))
        dataset = build_training_dataset(
            surface=str(options["surface"] or "home"),
            label_kind=str(options["label_kind"] or "purchase"),
            since=since,
            until=until,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"dataset built: id={dataset.id}, surface={dataset.surface}, rows={dataset.row_count}, positives={dataset.positive_count}, path={dataset.artifact_path}"
            )
        )
