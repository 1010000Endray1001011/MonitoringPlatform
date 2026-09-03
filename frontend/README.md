# Frontend — Uptime Monitoring Platform

React + TypeScript SPA consuming the Django REST API in the parent directory.
See the parent [`README.md`](../README.md) for the whole project's quick
start; this file only covers the frontend itself.

## Requirements

Node 18+ (developed against 18.19; Vite/React/TypeScript here don't need
anything newer, though a couple of dev-only tooling packages print an
`EBADENGINE` warning on 18 — harmless, everything still runs).

## Quick start

```bash
npm install
cp .env.example .env.local   # VITE_API_BASE_URL — defaults to http://localhost:8000
npm run dev
```

The backend must be running separately (`docker compose up` from the repo
root, or `manage.py runserver` — see the parent README) with
`CORS_ALLOWED_ORIGINS` including `http://localhost:5173`, which
`config/settings/local.py` already sets by default.

## Scripts

```bash
npm run dev             # Vite dev server
npm run build            # typecheck + production build
npm run typecheck        # tsc only, no build output
npm run lint              # ESLint
npm run format            # Prettier — writes
npm run format:check     # Prettier — check only, used in CI
npm run test              # Vitest, watch mode
npm run test:run          # Vitest, single run — used in CI
npm run generate-types    # regenerate src/api/schema.ts from the backend's OpenAPI schema
```

## Regenerating API types

`src/api/schema.ts` is generated from the backend's OpenAPI schema, not
hand-written — every request/response type the frontend uses comes from it
(re-exported through `src/api/types.ts`). Regenerate it after any backend
API change:

```bash
npm run generate-types                       # from a running backend at localhost:8000
node scripts/generate-types.mjs path/to.yaml  # from a schema file (what CI does)
```

## Auth

Access token lives in memory only (`src/auth/store.ts`, Zustand) — never in
`localStorage`. The refresh token is an httpOnly cookie the backend sets;
the frontend never reads it directly. `src/api/client.ts` handles the
401 → refresh → retry flow transparently, so most code just calls
`apiClient.get/post/patch/delete` without thinking about tokens at all.
`src/auth/useAuthBootstrap.ts` is what makes a page reload silently
re-authenticate via that cookie before `ProtectedRoute` decides whether to
redirect to `/login`.

## Project layout

```text
src/
  api/          typed client, generated schema, TanStack Query setup, MSW test mocks
  auth/         access-token store, silent-refresh bootstrap, logout
  routes/       one file per page
  theme/        React95 theme provider + global styles (styling itself is a later pass)
  test/         shared test setup and render helpers
```

## Testing

Vitest + React Testing Library, jsdom environment, MSW for mocking the
backend at the network layer — components call the real `apiClient`, tests
only control what the HTTP layer returns.
