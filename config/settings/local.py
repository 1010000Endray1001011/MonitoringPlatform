from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Vite's default dev server port — set explicitly rather than relying on
# .env so `npm run dev` next to `docker compose up` works with zero config.
CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
