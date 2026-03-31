from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from shopfront.recommendation.ml import activate_model, available_trainers, build_training_dataset, train_recommendation_model


class Command(BaseCommand):
    help = "Train and optionally activate a recommendation ranking model for a specific surface."

    def add_arguments(self, parser):
        parser.add_argument("--surface", default="home")
        parser.add_argument("--label-kind", default="purchase")
        parser.add_argument("--trainer", default="auto")
        parser.add_argument("--window-days", type=int, default=int(getattr(settings, "RECOMMENDATION_ML_TRAINING_WINDOW_DAYS", 30)))
        parser.add_argument("--epochs", type=int, default=20)
        parser.add_argument("--learning-rate", type=float, default=0.001)
        parser.add_argument("--l2", type=float, default=0.0001)
        parser.add_argument("--n-estimators", type=int, default=120)
        parser.add_argument("--max-depth", type=int, default=3)
        parser.add_argument("--activate", action="store_true")

    def handle(self, *args, **options):
        until = timezone.now()
        since = until - timedelta(days=int(options["window_days"] or 30))
        dataset = build_training_dataset(
            surface=str(options["surface"] or "home"),
            label_kind=str(options["label_kind"] or "purchase"),
            since=since,
            until=until,
        )
        model = train_recommendation_model(
            dataset,
            trainer=str(options["trainer"] or "auto"),
            epochs=int(options["epochs"] or 20),
            learning_rate=float(options["learning_rate"] or 0.001),
            l2=float(options["l2"] or 0.0001),
            n_estimators=int(options["n_estimators"] or 120),
            max_depth=int(options["max_depth"] or 3),
        )
        if bool(options.get("activate")) and model.status == model.Status.READY:
            activate_model(model)
        self.stdout.write(
            self.style.SUCCESS(
                f"model trained: id={model.id}, surface={model.surface}, version={model.version}, status={model.status}, "
                f"algorithm={model.algorithm}, trainers={available_trainers()}, metrics={model.metrics}"
            )
        )
