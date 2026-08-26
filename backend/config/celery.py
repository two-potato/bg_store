import os
from celery import Celery
from celery.schedules import crontab
from core.sentry import init_sentry

# Select settings module similar to ASGI based on DEBUG env
debug = os.getenv("DEBUG", "0") == "1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev" if debug else "config.settings.prod")
init_sentry(service_name="django-celery", enable_django=True, enable_celery=True)

app = Celery("servio")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "recommendations-refresh-popularity-hourly": {
        "task": "legacy_shopfront_state.tasks.refresh_recommendation_popularity",
        "schedule": crontab(minute=15),
        "args": ("7d", 60),
    },
    "recommendations-refresh-affinities-nightly": {
        "task": "legacy_shopfront_state.tasks.refresh_recommendation_affinities",
        "schedule": crontab(minute=20, hour=2),
        "args": (24,),
    },
    "recommendations-refresh-user-affinity-nightly": {
        "task": "legacy_shopfront_state.tasks.refresh_recommendation_user_affinity",
        "schedule": crontab(minute=35, hour=2),
        "args": (12,),
    },
    "recommendations-refresh-replenishment-nightly": {
        "task": "legacy_shopfront_state.tasks.refresh_recommendation_replenishment",
        "schedule": crontab(minute=45, hour=2),
        "args": (24,),
    },
    "recommendations-refresh-sets-hourly": {
        "task": "legacy_shopfront_state.tasks.refresh_recommendation_sets",
        "schedule": crontab(minute=25),
        "args": (8,),
    },
}
