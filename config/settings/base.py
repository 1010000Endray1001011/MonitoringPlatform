from datetime import timedelta
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

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
    "corsheaders",
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
    # First in, last out — every other middleware's request *and* response
    # phase runs with a request id already bound, including whatever
    # exception handling happens further down this list.
    "apps.common.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Must sit above CommonMiddleware (and anything else that can produce a
    # response) — otherwise responses generated before this point in the
    # chain never get the CORS headers added, and the browser blocks the
    # frontend from reading them even though the request itself succeeded.
    "corsheaders.middleware.CorsMiddleware",
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

# Underscored because Django 6.1 refuses to start when the deprecated
# EMAIL_BACKEND setting is defined alongside MAILERS ("Deprecated email
# settings are not allowed when MAILERS is defined"). The environment
# variable keeps the familiar name; only the settings-module name differs.
_EMAIL_BACKEND = env.str("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


def _build_mailer_options(backend: str, env: environ.Env) -> dict:
    """Connection options for MAILERS["default"], or {} for a backend that
    doesn't take any.

    Django hands this dict to the backend class as keyword arguments, and
    every backend rejects keys it doesn't recognise — the console backend
    used by default in development fails to start outright with
    "Unknown options 'host', 'port'". So these can't be set unconditionally:
    doing that breaks `docker compose up` for anyone who hasn't configured
    SMTP, which is everyone on a fresh clone.

    Underscore-prefixed so `from .base import *` in the per-environment
    settings modules doesn't re-export a helper as though it were a setting.
    """
    if backend != SMTP_BACKEND:
        return {}

    # Two ways to encrypt SMTP, and they're mutually exclusive: implicit TLS
    # on port 465 (use_ssl) or STARTTLS on 587 (use_tls). Defaulting use_tls
    # to the opposite of use_ssl means setting only EMAIL_USE_SSL=True does
    # the right thing, instead of silently colliding with a use_tls that
    # defaulted to True on its own.
    use_ssl = env.bool("EMAIL_USE_SSL", default=False)
    use_tls = env.bool("EMAIL_USE_TLS", default=not use_ssl)

    if use_ssl and use_tls:
        raise ImproperlyConfigured(
            "EMAIL_USE_SSL and EMAIL_USE_TLS are mutually exclusive — set one, not both. "
            "Use EMAIL_USE_SSL for port 465, EMAIL_USE_TLS for port 587."
        )

    return {
        "host": env.str("EMAIL_HOST", default="localhost"),
        "port": env.int("EMAIL_PORT", default=587),
        "username": env.str("EMAIL_HOST_USER", default=""),
        "password": env.str("EMAIL_HOST_PASSWORD", default=""),
        "use_ssl": use_ssl,
        "use_tls": use_tls,
        # Without this a hung SMTP server holds the Celery worker that's
        # sending the notification for as long as the OS lets the socket
        # sit there. The HTTP probe has had its own timeout from the start;
        # this is the same reasoning applied to the other outbound call.
        "timeout": env.int("EMAIL_TIMEOUT", default=10),
    }


MAILERS = {
    "default": {
        "BACKEND": _EMAIL_BACKEND,
        "OPTIONS": _build_mailer_options(_EMAIL_BACKEND, env),
    },
}

# Must match EMAIL_HOST_USER on providers that check it — Gmail rewrites or
# rejects a From it hasn't authenticated, and reports it as an opaque 5xx.
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


# Logging
# The "console" formatter is human-readable, meant for a developer's
# terminal — production.py swaps it for JsonFormatter so stdout there is
# machine-parseable by whatever log aggregator ends up reading it, without
# changing anything else (handlers, filters, levels stay identical).
# Every logger in the process propagates to the root handler below unless
# it sets propagate=False itself, so apps.*, integrations.*, django.*, and
# Celery's own loggers all end up going through the same request-id-tagged
# console output with zero per-app configuration.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.common.logging_utils.RequestIDLogFilter"},
    },
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env.str("DJANGO_LOG_LEVEL", default="INFO"),
    },
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
        "apps.common.throttling.FailOpenAnonRateThrottle",
        "apps.common.throttling.FailOpenUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "120/min",
        # Scoped rates below apply only to views/actions that opt in via
        # throttle_scope, on top of (not instead of) the blanket anon/user
        # rates above.
        "auth_token": "10/min",
        "monitor_check": "5/min",
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
    # Without this, drf-spectacular's tag auto-detection uses the first
    # path segment as the tag for every operation — since every path here
    # starts with /api/v1/, every single endpoint would land under one
    # undifferentiated "api" tag in Swagger UI instead of being grouped by
    # resource (Monitors, Incidents, ...).
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]+",
    "ENUM_NAME_OVERRIDES": {
        "DependencyStatusEnum": "apps.common.serializers.DEPENDENCY_STATUS_CHOICES",
        # Incident.status (OPEN/ACKNOWLEDGED/RESOLVED) collides on the bare
        # field name "status" with HealthCheckSerializer.status (ok/degraded)
        # — different choice sets, same field name, so drf-spectacular can't
        # merge them into one enum component and needs an explicit name.
        "IncidentStatusEnum": "apps.incidents.models.INCIDENT_STATUS_CHOICES",
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


# CORS
# Only the frontend origin(s) may call this API from a browser; there is no
# wildcard, and there cannot be one — CORS_ALLOW_CREDENTIALS=True (needed so
# the browser sends the httpOnly refresh cookie below) is rejected by every
# browser when paired with Access-Control-Allow-Origin: *.

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True


# Auth: refresh token cookie
# apps.accounts.views.CookieTokenObtainPairView/CookieTokenRefreshView read
# and write this cookie instead of putting the refresh token in the JSON
# response body — see apps/accounts/views.py for the full reasoning.

JWT_REFRESH_COOKIE_NAME = "refresh_token"
# Off by default (base/local/test all run over plain http); production.py
# turns this on, since a non-Secure cookie over https is sent in the clear
# on any http fallback and browsers increasingly refuse to set it at all.
JWT_REFRESH_COOKIE_SECURE = False
# Lax, not Strict: Strict would drop the cookie on a user opening the app
# from a link in another site/tab (a normal top-level GET navigation) until
# they navigate again from within the app. Lax still blocks the cookie from
# being attached to any cross-site POST, which is what actually matters for
# CSRF on the refresh endpoint.
JWT_REFRESH_COOKIE_SAMESITE = "Lax"


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
