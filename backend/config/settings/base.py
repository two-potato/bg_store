from pathlib import Path
from datetime import timedelta
import os
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = _env_bool("DEBUG", False)

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
    "site_title": "Admin",
    "site_header": "Admin",
    "site_brand": "Admin",
    "welcome_sign": "Welcome to admin",
    "show_sidebar": True,
    "navigation_expanded": True,
}

JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",
}

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.RequestContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if _env_bool("ENABLE_REQUEST_ACCESS_LOG", True):  # pragma: no cover - env-driven toggle
    # Keep this optional for high-load runs to reduce I/O bottlenecks.
    MIDDLEWARE.insert(-2, "core.middleware.RequestLoggingMiddleware")

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

# Cache
_cache_backend = (os.getenv("CACHE_BACKEND", "locmem") or "locmem").strip().lower()
if _cache_backend == "dummy":  # pragma: no cover - env-specific branch
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
elif _cache_backend == "locmem":  # pragma: no cover - env-specific branch
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": os.getenv("CACHE_LOCATION", "bg-shop-cache"),
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
            "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "bgshop"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("CACHE_URL", os.getenv("REDIS_URL", "redis://redis:6379/1")),
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
            "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "bgshop"),
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
                "shopfront.context_processors.header_categories",
                "shopfront.context_processors.site_settings",
                "shopfront.context_processors.favorites_state",
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
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("DRF_THROTTLE_ANON", "30/min"),
        "user": os.getenv("DRF_THROTTLE_USER", "120/min"),
    },
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

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Google provider keys (set in environment for production)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
        "APP": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
    }
}
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
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

# Analytics
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("TG_INIT_DATA_MAX_AGE_SECONDS", "300"))

# Login captcha / anti-bruteforce
LOGIN_CAPTCHA_THRESHOLD = int(os.getenv("LOGIN_CAPTCHA_THRESHOLD", "5"))
LOGIN_CAPTCHA_WINDOW_SECONDS = int(os.getenv("LOGIN_CAPTCHA_WINDOW_SECONDS", "900"))
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")

# Public observability/docs toggles
ENABLE_API_DOCS = _env_bool("ENABLE_API_DOCS", DEBUG)
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
ENABLE_CATALOG_RATING = _env_bool("ENABLE_CATALOG_RATING", DEBUG)

# Google Maps
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Elasticsearch
ES_URL = os.getenv("ES_URL", "http://es:9200")
ES_PRODUCTS_INDEX = os.getenv("ES_PRODUCTS_INDEX", "products")
ES_TIMEOUT_SECONDS = float(os.getenv("ES_TIMEOUT_SECONDS", "0.8"))

# Cache TTLs (seconds)
CACHE_TTL_HEADER_CATEGORIES = int(os.getenv("CACHE_TTL_HEADER_CATEGORIES", "900"))
CACHE_TTL_HOME = int(os.getenv("CACHE_TTL_HOME", "180"))
CACHE_TTL_CATALOG_FILTERS = int(os.getenv("CACHE_TTL_CATALOG_FILTERS", "900"))
CACHE_TTL_LIVE_SEARCH = int(os.getenv("CACHE_TTL_LIVE_SEARCH", "60"))
CACHE_TTL_ES_SEARCH = int(os.getenv("CACHE_TTL_ES_SEARCH", "120"))
CACHE_TTL_CATALOG_API = int(os.getenv("CACHE_TTL_CATALOG_API", "120"))
CACHE_TTL_COMMERCE_LOOKUPS = int(os.getenv("CACHE_TTL_COMMERCE_LOOKUPS", "600"))

# Admin email notifications (orders lifecycle)
ADMIN_NOTIFY_EMAILS = [
    e.strip()
    for e in os.getenv("ADMIN_NOTIFY_EMAILS", os.getenv("ADMIN_EMAIL", "")).split(",")
    if e.strip()
]
ADMIN_NOTIFY_TELEGRAM_IDS = [
    int(v.strip())
    for v in os.getenv("ADMIN_NOTIFY_TELEGRAM_IDS", "").split(",")
    if v.strip().lstrip("-").isdigit()
]
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@bgshop.local")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "0") == "1"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "30"))

# Marketplace service notifications
MARKETPLACE_SERVICE_ALERTS_ENABLED = _env_bool("MARKETPLACE_SERVICE_ALERTS_ENABLED", True)
ORDER_NEW_SLA_MINUTES = int(os.getenv("ORDER_NEW_SLA_MINUTES", "20"))
ORDER_NEW_SLA_ALERT_COOLDOWN_MINUTES = int(os.getenv("ORDER_NEW_SLA_ALERT_COOLDOWN_MINUTES", "60"))
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "5"))
LOW_STOCK_MAX_ITEMS = int(os.getenv("LOW_STOCK_MAX_ITEMS", "20"))
LOW_STOCK_ALERT_COOLDOWN_MINUTES = int(os.getenv("LOW_STOCK_ALERT_COOLDOWN_MINUTES", "180"))
FAKE_PAYMENT_STALE_MINUTES = int(os.getenv("FAKE_PAYMENT_STALE_MINUTES", "10"))
FAKE_PAYMENT_ALERT_COOLDOWN_MINUTES = int(os.getenv("FAKE_PAYMENT_ALERT_COOLDOWN_MINUTES", "120"))

CELERY_BEAT_SCHEDULE = {
    "service-alert-new-orders-sla": {
        "task": "orders.tasks.notify_new_orders_sla_breach",
        "schedule": timedelta(minutes=5),
    },
    "service-alert-low-stock": {
        "task": "orders.tasks.notify_low_stock_products",
        "schedule": timedelta(minutes=30),
    },
    "service-alert-stale-fake-payments": {
        "task": "orders.tasks.notify_stale_fake_payments",
        "schedule": timedelta(minutes=10),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CSRF trusted origins (needed when serving through a different port like 8080)
_csrf_env = [
    u.strip() for u in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if u.strip()
]
CSRF_TRUSTED_ORIGINS = _csrf_env or [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]

if not DEBUG:  # pragma: no cover - primarily exercised in production runtime
    _settings_module = os.getenv("DJANGO_SETTINGS_MODULE", "")
    _strict_settings = _env_bool(
        "ENFORCE_STRICT_SETTINGS",
        _settings_module.endswith(".prod"),
    )
    if _strict_settings:
        if SECRET_KEY in {"", "dev", "change-me"}:
            raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a strong value when DEBUG=0")
        if INTERNAL_TOKEN in {"", "change-me", "dev", "dev-secret"}:
            raise ImproperlyConfigured("INTERNAL_TOKEN must be set to a strong value when DEBUG=0")
        if ORDER_APPROVE_SECRET in {"", "change-me", "dev", "dev-secret"}:
            raise ImproperlyConfigured("ORDER_APPROVE_SECRET must be set to a strong value when DEBUG=0")
        if not TELEGRAM_BOT_TOKEN:
            raise ImproperlyConfigured("TELEGRAM_BOT_TOKEN must be configured when DEBUG=0")
        if "*" in ALLOWED_HOSTS:
            raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' when DEBUG=0")

# -------- Logging configuration --------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_JSON = os.getenv("LOG_JSON", "0") == "1"

# File logging configuration
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/app/logs/app.log")
_log_handlers = ["console", "file"]
_log_dir = os.path.dirname(LOG_FILE_PATH) or "."
try:
    os.makedirs(_log_dir, exist_ok=True)
except Exception:  # pragma: no cover - filesystem edge-case
    # Fall back to console-only logging when the file path is unavailable.
    _log_handlers = ["console"]

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
    "root": {"handlers": _log_handlers, "level": LOG_LEVEL},
    "loggers": {
        "django": {"level": "INFO"},
        "django.request": {"level": "WARNING"},
        "django.server": {"level": "WARNING"},
        "uvicorn": {"level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {"level": "INFO"},
        "django.db.backends": {
            "handlers": _log_handlers,
            "level": os.getenv("DB_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "celery": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "request": {
            "handlers": _log_handlers,
            "level": os.getenv("REQUEST_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "shopfront": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "commerce": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "users": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "orders": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "catalog": {
            "handlers": _log_handlers,
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

if "file" not in _log_handlers:  # pragma: no cover - fallback when file handler unavailable
    LOGGING["handlers"].pop("file", None)
