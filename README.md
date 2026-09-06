# Uptime Monitoring Platform

A service that periodically checks HTTP/HTTPS endpoints, tracks their health
over time, opens and resolves incidents automatically, and notifies you
(email or Telegram) when something goes down and again when it recovers.
Think a small, self-hosted UptimeRobot.

Backend: Django + Django REST Framework, PostgreSQL, Redis, and Celery, fully
documented via OpenAPI/Swagger — the running API is its own reference.
Frontend: a React 19 + TypeScript SPA with a Windows-95-plus-cyberpunk look
(see below). This file only covers getting both running and trying them out.

## What it does

- **Monitors** — register a URL, an HTTP method, an expected status code, a
  check interval (60s–1h) and a timeout; the engine polls it in the
  background and tracks consecutive successes/failures.
- **Incidents** — a monitor crossing its failure threshold opens an incident
  automatically; recovering closes it. Incidents can be acknowledged; a
  reconciliation job catches the rare case where one gets stuck open.
- **History & stats** — every check is recorded; hourly rollups power
  uptime/response-time summaries over 24h/7d/30d without scanning raw
  history. Raw checks are purged after they've been safely aggregated.
- **Notifications** — email and Telegram channels, verified with a real test
  message before they're trusted, then notified automatically on every
  incident open/resolve via a retrying background delivery queue.
- **SSRF-safe by design** — a monitor's URL is validated at write time and
  its target re-resolved and re-checked immediately before every single
  probe, so this can't be turned into a proxy for scanning internal
  infrastructure.

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

`web` runs migrations on startup and serves on `http://localhost:8000`.
`celery-worker` and `celery-beat` start alongside it and immediately begin
running the scheduled checks, hourly rollups, and retention jobs. `frontend`
builds and serves the React UI on `http://localhost:5173`.

- UI: `http://localhost:5173`
- Swagger UI: `http://localhost:8000/api/docs/`
- Health check: `http://localhost:8000/health`

## Quick start (local, no Docker)

Requires a local PostgreSQL and Redis.

```bash
poetry install
cp .env.example .env  # point DATABASE_URL / REDIS_URL at your local services
poetry run python manage.py migrate
poetry run python manage.py runserver
```

Run the background engine alongside it (nothing gets checked without these):

```bash
poetry run celery -A config worker -l info -Q checks,notifications,maintenance
poetry run celery -A config beat -l info
```

Frontend dev server, against the backend above:

```bash
cd frontend
npm install
cp .env.example .env  # VITE_API_BASE_URL defaults to http://localhost:8000
npm run dev
```

Serves on `http://localhost:5173` with hot reload.

## See it work in two minutes

```bash
poetry run python manage.py seed_demo
```

Creates a demo account (`demo@example.com` / `Demo-Pass123!`) with two
monitors against `https://example.com/` — one with a matching expected
status (stays healthy), one with a status it can never actually return
(guaranteed to fail). Log in via `/api/v1/auth/token`, watch
`GET /api/v1/incidents/` — within a couple of scheduler ticks the failing
monitor opens an incident on its own with no further action needed.

Same demo account through the UI instead: open `http://localhost:5173`, log
in with the credentials above, and the failing monitor's incident shows up
on the dashboard (a red "⚠ Open incident" flag with a neon glow) and on
`/incidents` — no curl needed.

<!-- TODO: dashboard screenshot — couldn't capture one in this sandbox
     (the Browser pane tool won't composite frames here); drop a real one
     at docs/screenshots/dashboard.png and reference it above. -->

## Try it by hand: register → monitor → incident → notification

```bash
BASE=http://localhost:8000

# 1. Register and log in
curl -sX POST $BASE/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "S0me-Str0ng-Pass", "password_confirm": "S0me-Str0ng-Pass"}'

TOKEN=$(curl -sX POST $BASE/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "S0me-Str0ng-Pass"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")
AUTH="Authorization: Bearer $TOKEN"

# 2. Add a notification channel and verify it (console backend by default —
# the "email" shows up in the server log, not a real inbox)
CHANNEL=$(curl -sX POST $BASE/api/v1/notification-channels/ -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"type": "EMAIL", "name": "My alerts", "config": {"email": "dev@example.com"}}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -sX POST $BASE/api/v1/notification-channels/$CHANNEL/verify/ -H "$AUTH"

# 3. Create a monitor that's guaranteed to fail, wired to that channel.
# failure_threshold=1 so a single failed check opens an incident right away
# instead of waiting for the default of two in a row.
MONITOR=$(curl -sX POST $BASE/api/v1/monitors/ -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"name\": \"Always down\", \"url\": \"https://example.com/\", \"expected_status\": 404, \"failure_threshold\": 1, \"notification_channel_ids\": [\"$CHANNEL\"]}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Ask for an immediate check instead of waiting for the schedule
curl -sX POST $BASE/api/v1/monitors/$MONITOR/check/ -H "$AUTH"

# 5. A few seconds later: check history, the open incident, and the monitor's own view of itself
curl -s $BASE/api/v1/monitors/$MONITOR/checks/ -H "$AUTH"
curl -s "$BASE/api/v1/incidents/?monitor=$MONITOR" -H "$AUTH"
curl -s $BASE/api/v1/monitors/$MONITOR/ -H "$AUTH"
```

Everything above (and every other endpoint — pause/resume, uptime stats,
acknowledging an incident, listing channels) is documented with request/
response examples at `/api/docs/`.

## Rate limits

| Scope | Limit |
|---|---|
| Anonymous requests | 20/min per IP |
| Authenticated requests | 120/min per user |
| `POST /auth/token` | 10/min per IP |
| `POST /monitors/{id}/check` | 5/min per user |

The last one isn't a formality — that endpoint makes this service send a
request to a URL of the caller's choosing. If the rate-limit backend
(Redis) itself is unreachable, requests are allowed through rather than
turning a Redis outage into a full API outage.

## Sanity load check

50 monitors at the minimum 60s interval, all due at the same moment (the
worst case for one dispatcher tick — in steady state they'd be spread out
over the interval, not stacked), against a local PostgreSQL over a loopback
connection:

| Scenario | Time |
|---|---|
| One dispatch tick, 50 due monitors (claim + all 50 checks) | ~770 ms total, ~15 ms/check |
| One dispatch tick, nothing due (the common case every 30s) | ~4 ms |

The dispatcher runs every 30s regardless of load, so a ~0.8s tick has
enormous headroom before it could ever run long enough to overlap the next
one. The real limit at this design's scale isn't the scheduler — it's how
many monitors can be checked serially per worker between ticks; horizontal
scaling is adding more `celery-worker` replicas on the `checks` queue.

## Tests

```bash
poetry run pytest --cov
```

Tests run against `config.settings.test`: Celery in eager mode, Redis
replaced with `LocMemCache`, and outbound sockets disabled outside
`127.0.0.1`/`::1` (`pytest-socket`) — a test that reaches for the real
network fails loudly instead of flaking. A local PostgreSQL is still
required; point `DATABASE_URL` at it.

## Tooling

```bash
poetry run pre-commit run --all-files   # black + isort + ruff + hygiene hooks
poetry run pre-commit install           # run automatically on every commit
poetry run python manage.py spectacular --file schema.yaml --fail-on-warn  # OpenAPI schema sanity check
```

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults. The
notable ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` / `REDIS_URL` | Standard connection URLs. |
| `CELERY_TASK_ALWAYS_EAGER` | `True` runs tasks inline with no worker — local debugging only. |
| `MONITORING_ALLOW_PRIVATE_TARGETS` | Lets monitors target private/internal addresses. Must stay `False` outside local/test — this is the SSRF guard's off switch. Production refuses to start if it's `True`. |
| `TELEGRAM_BOT_TOKEN` | One bot for the whole platform; each channel only stores which `chat_id` to message. |
| `EMAIL_BACKEND` | Defaults to the console backend — notifications print to the server log instead of sending real email. |

See [`frontend/.env.example`](frontend/.env.example) for the frontend's own
(much shorter) list — just `VITE_API_BASE_URL`, baked into the static bundle
at build time (Vite inlines `import.meta.env.*` at build, not at container
start), which is why Docker Compose passes it as a build arg rather than a
runtime environment variable.

Never commit a real `.env` — it's gitignored.

## Project layout

```text
config/           settings (base/local/test/production), celery.py, urls.py
apps/
    common/       cross-cutting infra: exceptions, pagination, throttling,
                  logging/request-id middleware, health check, demo seed command
    accounts/     custom User (email login), JWT auth
    monitors/     Monitor CRUD, SSRF-guarded URLs, pause/resume, uptime stats
    checks/       the monitoring engine: scheduler, probe execution, history,
                  hourly rollups, retention
    incidents/    incident lifecycle (open/acknowledge/resolve), reconciliation
    notifications/ channels, verification, outbox-based delivery with retry
integrations/     Django-independent clients: HTTP probe (+ SSRF re-check),
                  Telegram, email — none of them ever raise; every outcome
                  comes back as a typed result object
tests/            unit / services / api / tasks / integration
docker/           Dockerfile, entrypoint.sh
frontend/         React 19 + TypeScript SPA (Vite, TanStack Query, React95)
    src/api/      typed fetch client + TanStack Query hooks; types generated
                  from the backend's own OpenAPI schema, not hand-written
    src/auth/     access token (in-memory only) + silent-refresh bootstrap
    src/routes/   one file per screen (dashboard, monitor detail, incidents,
                  channels, login/register, 404)
    src/components/  shared UI pieces (status badges, forms, nav)
    src/theme/    the retro Windows-95 + cyberpunk-accent theme
```
