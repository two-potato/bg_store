"""Transitional owner for recommendation jobs that still write legacy Django state.

The algorithms are still delegated to the historical implementation during the
migration window. Celery Beat and new callers use this module as the canonical
task namespace; ``shopfront.tasks`` remains registered only for queue-drain
compatibility until the implementation itself is extracted.
"""

from celery import shared_task


def _legacy_tasks():
    from shopfront import tasks

    return tasks


@shared_task
def refresh_recommendation_popularity(window: str = "7d", limit: int = 60):
    return _legacy_tasks().refresh_recommendation_popularity.run(window, limit)


@shared_task
def refresh_recommendation_affinities(limit_per_product: int = 24):
    return _legacy_tasks().refresh_recommendation_affinities.run(limit_per_product)


@shared_task
def refresh_recommendation_user_affinity(limit_per_dimension: int = 12):
    return _legacy_tasks().refresh_recommendation_user_affinity.run(limit_per_dimension)


@shared_task
def refresh_recommendation_replenishment(limit_per_user: int = 24):
    return _legacy_tasks().refresh_recommendation_replenishment.run(limit_per_user)


@shared_task
def refresh_recommendation_sets(limit: int = 8):
    return _legacy_tasks().refresh_recommendation_sets.run(limit)


@shared_task
def refresh_recommendation_ml_features(user_limit: int = 1000, product_limit: int = 2000):
    return _legacy_tasks().refresh_recommendation_ml_features.run(user_limit, product_limit)


@shared_task
def train_recommendation_ml_surface(
    surface: str = "home",
    label_kind: str = "purchase",
    activate: bool = True,
):
    return _legacy_tasks().train_recommendation_ml_surface.run(surface, label_kind, activate)
