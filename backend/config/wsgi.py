import os
from core.sentry import init_sentry
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')
init_sentry(service_name="django-wsgi", enable_django=True)
application = get_wsgi_application()
