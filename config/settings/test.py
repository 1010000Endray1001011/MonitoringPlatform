from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

MAILERS = {"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

MONITORING_ALLOW_PRIVATE_TARGETS = True
