from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env.str("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])


# Application definition

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "django_filters",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.monitors",
    "apps.checks",
    "apps.incidents",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases

DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration

MAILERS = {
    "default": {
        "BACKEND": env.str(
            "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
        ),
    },
}
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="alerts@monitoringplatform.local")


# Cache / Redis
# Real role: Celery broker, distributed locks (checks.services), DRF throttling.

REDIS_URL = env.str("REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}


# Django REST Framework

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.domain_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "120/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Uptime Monitoring Platform API",
    "DESCRIPTION": (
        "API / URL monitoring platform: periodic HTTP checks, incident detection "
        "and notification delivery."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "DependencyStatusEnum": "apps.common.serializers.DEPENDENCY_STATUS_CHOICES",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# Celery
# Beat schedule and queue routing live in config/celery.py.

CELERY_BROKER_URL = REDIS_URL
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_DEFAULT_QUEUE = "checks"
CELERY_TASK_ROUTES = {
    "apps.checks.tasks.*": {"queue": "checks"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.checks.tasks.rollup_hourly_stats": {"queue": "maintenance"},
    "apps.checks.tasks.purge_old_check_results": {"queue": "maintenance"},
    "apps.incidents.tasks.*": {"queue": "maintenance"},
}


# Domain configuration
# Deliberately kept as settings (not hardcoded) so tests can override them via
# @override_settings instead of monkeypatching module constants.

MONITORING_MIN_INTERVAL_SECONDS = 60
MONITORING_MAX_TIMEOUT_SECONDS = 30
MONITORING_DEFAULT_MONITOR_QUOTA = 20
MONITORING_MAX_RESPONSE_BYTES = 1 * 1024 * 1024  # 1 MB
MONITORING_RAW_RETENTION_DAYS = 7
MONITORING_ALLOWED_PORTS = [80, 443, 8080, 8443]
MONITORING_ALLOW_PRIVATE_TARGETS = env.bool("MONITORING_ALLOW_PRIVATE_TARGETS", default=False)

TELEGRAM_BOT_TOKEN = env.str("TELEGRAM_BOT_TOKEN", default="")
