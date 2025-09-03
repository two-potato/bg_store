import os
from django.core.asgi import get_asgi_application
from django.conf import settings

# Выбираем настройки по переменной окружения DEBUG
debug = os.getenv('DEBUG', '0') == '1'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev' if debug else 'config.settings.prod')
_django_app = get_asgi_application()

try:
    # В dev обслуживаем статику самим Django (ASGI handler)
    if settings.DEBUG:
        from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
        application = ASGIStaticFilesHandler(_django_app)
    else:
        application = _django_app
except Exception:
    # Фоллбек на обычное приложение, если что-то пошло не так
    application = _django_app
