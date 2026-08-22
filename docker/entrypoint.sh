#!/bin/sh
set -e

python - <<'PYEOF'
import socket
import time

import environ

env = environ.Env()
db = env.db_url("DATABASE_URL")
host, port = db["HOST"], int(db["PORT"] or 5432)

for _ in range(30):
    try:
        with socket.create_connection((host, port), timeout=1):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"Database at {host}:{port} not reachable after 30s")
PYEOF

# Only the web service runs migrations, to avoid concurrent migration races
# between web/celery-worker/celery-beat starting up at the same time.
if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
