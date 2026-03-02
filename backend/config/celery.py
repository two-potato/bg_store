import os
from celery import Celery

# Select settings module similar to ASGI based on DEBUG env
debug = os.getenv("DEBUG", "0") == "1"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev" if debug else "config.settings.prod")

app = Celery("bad_guys")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
