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

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")

if not CORS_ALLOWED_ORIGINS:
    raise RuntimeError("CORS_ALLOWED_ORIGINS must be set explicitly in production.")

# base.py defaults this to False since local/test run over plain http — the
# refresh cookie must be Secure wherever it can actually travel over https.
JWT_REFRESH_COOKIE_SECURE = True

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Same handlers/filters/root as base.py — only the formatter changes, so
# stdout here is one JSON object per line instead of the human-readable
# line format local/test use. A full reassignment (not a nested mutation
# of the dict from base.py) since `from .base import *` binds this module's
# LOGGING name to the *same* dict object base.py built, and settings
# modules elsewhere in this project (see CACHES in test.py) follow the
# same reassign-don't-mutate convention for exactly that reason.
LOGGING = {
    **LOGGING,  # noqa: F405
    "formatters": {
        "console": {"()": "apps.common.logging_utils.JsonFormatter"},
    },
}
