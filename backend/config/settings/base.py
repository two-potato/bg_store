from pathlib import Path
from datetime import timedelta
import os
import warnings
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]
_UNSAFE_PLACEHOLDER_SECRETS = {"", "change-me", "dev", "dev-secret"}

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


DEBUG = _env_bool("DEBUG", False)
ALLOWED_HOSTS = _env_csv("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

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
    "promotions",
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

if _env_bool("ENABLE_REQUEST_ACCESS_LOG", False):  # pragma: no cover - env-driven toggle
    # Keep this optional for high-load runs to reduce I/O bottlenecks.
    MIDDLEWARE.insert(-2, "core.middleware.RequestLoggingMiddleware")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = _env_csv("CORS_ALLOWED_ORIGINS")

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
_default_cache_backend = "redis" if (os.getenv("REDIS_URL") or "").strip() else "locmem"
_cache_backend = (os.getenv("CACHE_BACKEND", _default_cache_backend) or _default_cache_backend).strip().lower()
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
            "LOCATION": os.getenv("CACHE_LOCATION", "servio-cache"),
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
            "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "servio"),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("CACHE_URL", os.getenv("REDIS_URL", "redis://redis:6379/1")),
            "TIMEOUT": int(os.getenv("CACHE_DEFAULT_TIMEOUT", "300")),
            "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "servio"),
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
                "shopfront.context_processors.compare_state",
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
    "TITLE": "Servio API",
    "VERSION": "1.0.0",
    "DESCRIPTION": (
        "B2B API для маркетплейса HoReCa.\n\n"
        "Основные группы:\n"
        "- Users: профиль текущего пользователя и Telegram WebApp auth\n"
        "- Commerce: юрлица, адреса доставки, Dadata lookup и административные действия\n"
        "- Catalog: бренды, серии, категории и товары\n"
        "- Orders: создание, просмотр и служебные approve/reject операции\n\n"
        "- Search: контрактный слой поиска и suggest/facet surfaces\n"
        "- Recommendations: контрактный слой recommendation surfaces\n\n"
        "Аутентификация:\n"
        "- Большинство методов требуют Bearer JWT access token\n"
        "- `/api/users/auth/tg-webapp/` выдаёт access token для Telegram WebApp\n"
        "- Внутренние order approve/reject методы используют `X-Internal-Token`\n"
    ),
    "SERVERS": [
        {"url": "http://localhost:8080", "description": "Local dev via Nginx"},
        {"url": "https://complaexbar.ru", "description": "Production"},
    ],
    "TAGS": [
        {"name": "Users", "description": "Профиль пользователя и Telegram-аутентификация"},
        {"name": "Commerce", "description": "Юрлица, адреса доставки и внешние справочники"},
        {"name": "Commerce Admin", "description": "Административные действия по заявкам и юрлицам"},
        {"name": "Catalog", "description": "Публичный каталог брендов, категорий, серий и товаров"},
        {"name": "Orders", "description": "Создание и чтение заказов компании"},
        {"name": "Internal Orders", "description": "Внутренние approve/reject операции для заказов"},
        {"name": "Search", "description": "Контрактный слой поиска storefront и фасеты/suggestions"},
        {"name": "Recommendations", "description": "Контрактный слой recommendation surfaces storefront"},
        {"name": "Schema", "description": "OpenAPI schema и UI-документация"},
    ],
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
    },
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
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
GTM_CONTAINER_ID = os.getenv("GTM_CONTAINER_ID", "GTM-N36D6TRQ").strip()
TRUST_X_FORWARDED_FOR = _env_bool("TRUST_X_FORWARDED_FOR", False)
ENABLE_DEMO_PAYMENTS = _env_bool("ENABLE_DEMO_PAYMENTS", DEBUG)
CACHE_SUGGESTION_CANDIDATES = _env_bool("CACHE_SUGGESTION_CANDIDATES", True)
SEARCH_SUGGESTION_CACHE_TTL = int(os.getenv("SEARCH_SUGGESTION_CACHE_TTL", "900"))
CATALOG_FILTER_BRAND_LIMIT = int(os.getenv("CATALOG_FILTER_BRAND_LIMIT", "24"))
CATALOG_FILTER_TAG_LIMIT = int(os.getenv("CATALOG_FILTER_TAG_LIMIT", "24"))
CATALOG_FILTER_CATEGORY_DEPTH = int(os.getenv("CATALOG_FILTER_CATEGORY_DEPTH", "1"))

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
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "").strip()
POSTHOG_HOST = os.getenv("POSTHOG_HOST", "https://app.posthog.com").strip()
CLARITY_PROJECT_ID = os.getenv("CLARITY_PROJECT_ID", "").strip()
ANALYTICS_REQUIRE_CONSENT = _env_bool("ANALYTICS_REQUIRE_CONSENT", not DEBUG)
ANALYTICS_INGEST_RATE_LIMIT = int(os.getenv("ANALYTICS_INGEST_RATE_LIMIT", "180"))
ANALYTICS_INGEST_WINDOW_SECONDS = int(os.getenv("ANALYTICS_INGEST_WINDOW_SECONDS", "60"))

# Search readiness
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "opensearch").strip().lower()
OPENSEARCH_ENABLED = _env_bool("OPENSEARCH_ENABLED", True)
SEMANTIC_SEARCH_ENABLED = _env_bool("SEMANTIC_SEARCH_ENABLED", False)
SEARCH_QUERY_REWRITE_ENABLED = _env_bool("SEARCH_QUERY_REWRITE_ENABLED", True)
SEARCH_KEYBOARD_LAYOUT_CORRECTION_ENABLED = _env_bool("SEARCH_KEYBOARD_LAYOUT_CORRECTION_ENABLED", True)
SEARCH_RERANK_ENABLED = _env_bool("SEARCH_RERANK_ENABLED", True)
SEMANTIC_SEARCH_BACKEND = os.getenv("SEMANTIC_SEARCH_BACKEND", "hybrid-db").strip().lower()
SEARCH_SERVICE_MODE = os.getenv("SEARCH_SERVICE_MODE", "django-inline").strip().lower()
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://search-api:8010").strip().rstrip("/")
SEARCH_SERVICE_TIMEOUT_SECONDS = float(os.getenv("SEARCH_SERVICE_TIMEOUT_SECONDS", "0.8"))
RECOMMENDATION_SERVICE_MODE = os.getenv("RECOMMENDATION_SERVICE_MODE", "django-inline").strip().lower()
RECOMMENDATION_SERVICE_URL = os.getenv("RECOMMENDATION_SERVICE_URL", "http://recommendation-api:8011").strip().rstrip("/")
RECOMMENDATION_SERVICE_TIMEOUT_SECONDS = float(os.getenv("RECOMMENDATION_SERVICE_TIMEOUT_SECONDS", "0.8"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("TG_INIT_DATA_MAX_AGE_SECONDS", "300"))

# Login captcha / anti-bruteforce
LOGIN_CAPTCHA_THRESHOLD = int(os.getenv("LOGIN_CAPTCHA_THRESHOLD", "5"))
LOGIN_CAPTCHA_WINDOW_SECONDS = int(os.getenv("LOGIN_CAPTCHA_WINDOW_SECONDS", "900"))
AUTH_LOGIN_RATE_LIMIT_ATTEMPTS = int(os.getenv("AUTH_LOGIN_RATE_LIMIT_ATTEMPTS", "30"))
AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "3600"))
AUTH_REGISTER_RATE_LIMIT_ATTEMPTS = int(os.getenv("AUTH_REGISTER_RATE_LIMIT_ATTEMPTS", "20"))
AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS", "3600"))
TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY", "1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA")

# Public observability/docs toggles
ENABLE_API_DOCS = _env_bool("ENABLE_API_DOCS", DEBUG)
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
ENABLE_CATALOG_RATING = _env_bool("ENABLE_CATALOG_RATING", True)

# Google Maps
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

if DEBUG:
    if INTERNAL_TOKEN in _UNSAFE_PLACEHOLDER_SECRETS:
        warnings.warn("DEBUG mode is using placeholder INTERNAL_TOKEN", RuntimeWarning)
    if ORDER_APPROVE_SECRET in _UNSAFE_PLACEHOLDER_SECRETS:
        warnings.warn("DEBUG mode is using placeholder ORDER_APPROVE_SECRET", RuntimeWarning)

# OpenSearch
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://opensearch:9200")
OPENSEARCH_PRODUCTS_INDEX = os.getenv("OPENSEARCH_PRODUCTS_INDEX", "products")
OPENSEARCH_TIMEOUT_SECONDS = float(os.getenv("OPENSEARCH_TIMEOUT_SECONDS", "0.8"))
OPENSEARCH_ENABLED = _env_bool("OPENSEARCH_ENABLED", True)

# Cache TTLs (seconds)
CACHE_TTL_HEADER_CATEGORIES = int(os.getenv("CACHE_TTL_HEADER_CATEGORIES", "900"))
CACHE_TTL_HOME = int(os.getenv("CACHE_TTL_HOME", "180"))
CACHE_TTL_CATALOG_FILTERS = int(os.getenv("CACHE_TTL_CATALOG_FILTERS", "900"))
CACHE_TTL_LIVE_SEARCH = int(os.getenv("CACHE_TTL_LIVE_SEARCH", "60"))
CACHE_TTL_OPENSEARCH_SEARCH = int(os.getenv("CACHE_TTL_OPENSEARCH_SEARCH", "120"))
CACHE_TTL_CATALOG_API = int(os.getenv("CACHE_TTL_CATALOG_API", "120"))
CACHE_TTL_COMMERCE_LOOKUPS = int(os.getenv("CACHE_TTL_COMMERCE_LOOKUPS", "600"))
CACHE_TTL_PDP_SUMMARY = int(os.getenv("CACHE_TTL_PDP_SUMMARY", "300"))
CACHE_TTL_PDP_RECOMMENDATIONS = int(os.getenv("CACHE_TTL_PDP_RECOMMENDATIONS", "180"))
RECOMMENDATION_ML_ENABLED = _env_bool("RECOMMENDATION_ML_ENABLED", True)
RECOMMENDATION_ML_ROLLOUT_PERCENT = int(os.getenv("RECOMMENDATION_ML_ROLLOUT_PERCENT", "0"))
RECOMMENDATION_ML_SURFACES = [
    value.strip()
    for value in os.getenv("RECOMMENDATION_ML_SURFACES", "home,catalog").split(",")
    if value.strip()
]
RECOMMENDATION_ML_TRAINING_WINDOW_DAYS = int(os.getenv("RECOMMENDATION_ML_TRAINING_WINDOW_DAYS", "30"))

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
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@servio.local")
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

if RECOMMENDATION_ML_ENABLED:
    CELERY_BEAT_SCHEDULE.update(
        {
            "recommendation-ml-refresh-features": {
                "task": "shopfront.tasks.refresh_recommendation_ml_features",
                "schedule": timedelta(hours=6),
            },
            "recommendation-ml-train-home": {
                "task": "shopfront.tasks.train_recommendation_ml_surface",
                "schedule": timedelta(days=1),
                "kwargs": {"surface": "home", "label_kind": "purchase", "activate": True},
            },
            "recommendation-ml-train-catalog": {
                "task": "shopfront.tasks.train_recommendation_ml_surface",
                "schedule": timedelta(days=1),
                "kwargs": {"surface": "catalog", "label_kind": "purchase", "activate": True},
            },
        }
    )

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CSRF trusted origins (needed when serving through a different port like 8080)
_csrf_env = _env_csv("CSRF_TRUSTED_ORIGINS")
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
        _unsafe_placeholders = {"", "change-me", "dev", "dev-secret"}
        _localhost_hosts = {"localhost", "127.0.0.1", "0.0.0.0"}
        if SECRET_KEY in {"", "dev", "change-me"}:
            raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a strong value when DEBUG=0")
        if INTERNAL_TOKEN in _unsafe_placeholders:
            raise ImproperlyConfigured("INTERNAL_TOKEN must be set to a strong value when DEBUG=0")
        if ORDER_APPROVE_SECRET in _unsafe_placeholders:
            raise ImproperlyConfigured("ORDER_APPROVE_SECRET must be set to a strong value when DEBUG=0")
        if METRICS_TOKEN in _unsafe_placeholders:
            raise ImproperlyConfigured("METRICS_TOKEN must be set to a strong value when DEBUG=0")
        if not TELEGRAM_BOT_TOKEN:
            raise ImproperlyConfigured("TELEGRAM_BOT_TOKEN must be configured when DEBUG=0")
        if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
            raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' when DEBUG=0")
        if any(host in _localhost_hosts for host in ALLOWED_HOSTS):
            raise ImproperlyConfigured("ALLOWED_HOSTS must not contain localhost-only hosts when DEBUG=0")
        if not _csrf_env:
            raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be explicitly configured when DEBUG=0")
        if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
            raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must use https:// origins when DEBUG=0")
        if any("localhost" in origin or "127.0.0.1" in origin for origin in CSRF_TRUSTED_ORIGINS):
            raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must not contain local origins when DEBUG=0")

# -------- Logging configuration --------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_JSON = os.getenv("LOG_JSON", "0") == "1"

# File logging configuration
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "/app/logs/app.log")


def _can_use_log_file(path: str) -> bool:
    log_dir = os.path.dirname(path) or "."
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(path, "a", encoding="utf-8"):
            pass
    except OSError:
        return False
    return True


_log_handlers = ["console", "file"] if _can_use_log_file(LOG_FILE_PATH) else ["console"]

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
        "core.notifications": {
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
