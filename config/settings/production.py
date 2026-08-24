from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

if not ALLOWED_HOSTS:
    raise RuntimeError("ALLOWED_HOSTS must be set explicitly in production.")

if MONITORING_ALLOW_PRIVATE_TARGETS:  # noqa: F405
    raise RuntimeError(
        "MONITORING_ALLOW_PRIVATE_TARGETS must never be enabled in production "
        "— it disables the SSRF guard that keeps monitors off private networks."
    )

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
