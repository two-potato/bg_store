from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "django_filters",
    "django_fsm",
    # Social auth
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "core",
    "users",
    "commerce",
    "catalog",
    "orders",
    "shopfront",
]

JAZZMIN_SETTINGS = {
    "site_title": "BG Shop Admin",
    "site_header": "Bad Guys Shop",
    "site_brand": "BG Shop",
    "welcome_sign": "Управление магазином",
    "copyright": "Bad Guys Shop",
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "orders",
        "commerce",
        "catalog",
        "users",
    ],
    "icons": {
        "orders.Order": "fas fa-cart-shopping",
        "orders.OrderItem": "fas fa-box",
        "commerce.LegalEntity": "fas fa-building",
        "commerce.DeliveryAddress": "fas fa-location-dot",
        "catalog.Product": "fas fa-tags",
        "users.User": "fas fa-user",
    },
    "custom_links": {},
    "show_ui_builder": False,
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Request logging after auth to have user context
    "core.middleware.RequestContextMiddleware",
    "core.middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "shop"),
        "USER": os.getenv("POSTGRES_USER", "shop"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "shop"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        # Persistent connections for better performance
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
    }
}

AUTH_USER_MODEL = "users.User"
SITE_ID = 1

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "shopfront.context_processors.cart_badge",
            ],
        },
    }
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Bad Guys Shop API",
    "VERSION": "1.0.0",
}

# django-allauth basic config (Google)
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)
# allauth v64+ recommended settings
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/account/login/"

# Google provider keys (set in environment for production)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        }
    }
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [ BASE_DIR / "static" ]
MEDIA_URL = "/media/"
MEDIA_ROOT = os.getenv("MEDIA_ROOT", BASE_DIR / "media")

# Celery
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_TIMEZONE = "Europe/Berlin"

# Integrations
INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "change-me")
ORDER_APPROVE_SECRET = os.getenv("ORDER_APPROVE_SECRET", "dev-secret")
BOT_BASE_URL = os.getenv("BOT_BASE_URL", "http://bot:8080")
# Separate bots (TWA and notifications)
BOT_TWA_URL = os.getenv("BOT_TWA_URL", BOT_BASE_URL)
BOT_NOTIFY_URL = os.getenv("BOT_NOTIFY_URL", BOT_BASE_URL)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Google Maps
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Admin email notifications (orders lifecycle)
ADMIN_NOTIFY_EMAILS = [
    e.strip() for e in os.getenv("ADMIN_NOTIFY_EMAILS", os.getenv("ADMIN_EMAIL", "")).split(",") if e.strip()
]
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@bgshop.local")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "30"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CSRF trusted origins (needed when serving through a different port like 8080)
_csrf_env = [u.strip() for u in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if u.strip()]
CSRF_TRUSTED_ORIGINS = _csrf_env or [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]

# -------- Logging configuration --------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_JSON = os.getenv("LOG_JSON", "0") == "1"

# File logging configuration
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/app/logs/app.log")
try:
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
except Exception:
    # If directory creation fails, continue with console logging only
    pass

_LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s user=%(user)s] "
    "%(message)s"
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "core.logging_utils.RequestContextFilter",
        }
    },
    "formatters": {
        "plain": {
            "format": _LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json": {
            "()": "core.logging_utils.JSONFormatter",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context"],
            "formatter": "json" if LOG_JSON else "plain",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_FILE_PATH,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
            "filters": ["request_context"],
            "formatter": "json" if LOG_JSON else "plain",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"level": "INFO"},
        "django.request": {"level": "WARNING"},
        "django.server": {"level": "WARNING"},
        "uvicorn": {"level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "INFO"},
        "django.db.backends": {"handlers": ["console", "file"], "level": os.getenv("DB_LOG_LEVEL", "WARNING"), "propagate": False},
        "celery": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "request": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "shopfront": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "commerce": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "users": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "orders": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
        "catalog": {"handlers": ["console", "file"], "level": LOG_LEVEL, "propagate": False},
    },
}
