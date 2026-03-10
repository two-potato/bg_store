import os
from celery import Celery
from core.sentry import init_sentry

# Select settings module similar to ASGI based on DEBUG env
debug = os.getenv("DEBUG", "0") == "1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev" if debug else "config.settings.prod")
init_sentry(service_name="django-celery", enable_django=True, enable_celery=True)

app = Celery("servio")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
