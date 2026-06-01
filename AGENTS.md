# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

Amnezia is a self-hosted VPN management system built around AmneziaWG.

- `panel/backend/`: FastAPI management API, SQLAlchemy/Alembic, RabbitMQ job publishing.
- `panel/worker/`: async worker that consumes RabbitMQ jobs and calls backend/node APIs.
- `panel/admin-frontend/`: Vue 3 admin SPA built with Vite.
- `panel/user-frontend/`: Vue 3 self-service user page built with Vite.
- `node/agent/`: FastAPI agent that runs on VPN nodes and controls AmneziaWG.
- `panel/docker-compose.yml` and `node/docker-compose.yml`: local/container deployments.

Read `README.md`, `CONTRIBUTING.md`, and `panel/worker/CONTRACT.md` before changing behavior
that crosses service boundaries.

## Repository rules

- Keep changes focused and minimal. Do not refactor unrelated code while fixing a bug or adding a
  feature.
- Do not commit secrets, local runtime data, generated dependency folders, build outputs, caches, or
  VPN node configs. In particular, avoid `node/config/*.conf`, `node/config/*.lock`, `panel/data/`,
  `.venv/`, `node_modules/`, and frontend `dist/` directories.
- Preserve public API contracts between backend, worker, node agent, and frontends. Update tests and
  docs when a contract changes.
- Prefer existing patterns in the target module over introducing new abstractions.
- Use Docker Compose only for integration/manual checks that need live services.
- Never add co-authors, `Co-authored-by` trailers, AI attribution footers, or assistant/bot
  attribution to commits.

## Python services

Python projects use Python 3.14+, `uv`, Ruff, `ty`, and pytest.

Setup and common commands:

```bash
cd panel/backend && uv sync --dev
cd panel/worker && uv sync --dev
cd node/agent && uv sync --dev
```

Run checks for the service you changed:

```bash
uv run --directory panel/backend ruff check --fix
uv run --directory panel/backend ruff format
uv run --directory panel/backend ty check --python .venv/bin/python
uv run --directory panel/backend pytest -q

uv run --directory panel/worker ruff check --fix
uv run --directory panel/worker ruff format
uv run --directory panel/worker ty check --python .venv/bin/python
uv run --directory panel/worker pytest -q

uv run --directory node/agent ruff check --fix
uv run --directory node/agent ruff format
uv run --directory node/agent ty check --python .venv/bin/python
uv run --directory node/agent pytest -q
```

Style notes:

- Ruff line length is 100.
- Python format uses single quotes and spaces.
- Backend and worker first-party package is `app`; node agent has no configured first-party package.
- Tests use pytest with `asyncio_mode = "auto"`.
- Avoid broad exception handling unless required by an external boundary or contract.

## Frontend apps

Both frontends are Vue 3 + Vite + TypeScript projects with ESLint and Prettier.

Setup:

```bash
cd panel/admin-frontend && npm install
cd panel/user-frontend && npm install
```

Run checks for the app you changed:

```bash
npm run lint
npm run build
npm run format
```

Frontend guidance:

- Keep API access patterns centralized in existing API modules where possible.
- Match existing component style, routing, and state patterns.
- Do not add UI dependencies unless the existing stack cannot reasonably solve the problem.

## Backend, worker, and node contracts

- Worker job payloads, RabbitMQ topology, retry behavior, and internal backend endpoints are described
  in `panel/worker/CONTRACT.md`.
- Backend worker-only routes live under `/internal/worker` and require bearer authentication.
- The node agent must not be assumed to be publicly reachable; README states it should be firewalled
  to the management server.
- When changing job commands, operation state, node snapshots, or provisioning/sync behavior, update
  backend tests, worker tests, and `panel/worker/CONTRACT.md` together.

## Migrations and persistence

- Backend database migrations live in `panel/backend/migrations/versions/`.
- Model/schema changes should include an Alembic migration and tests covering the persisted behavior.
- Do not edit old migrations unless correcting an unreleased local draft; add a new migration for
  existing history.

## Verification expectations

Before handing off changes:

- Run the narrowest relevant format, lint, type, and test commands for changed modules.
- For frontend changes, run `npm run lint` and `npm run build` in the changed frontend app.
- For Python changes, run Ruff, `ty`, and pytest in the changed Python project.
- For cross-service behavior, also exercise the behavior through the appropriate surface: HTTP API,
  worker handler, frontend route, or Docker Compose service.
- If a command cannot be run because dependencies or services are missing, report that explicitly with
  the exact command that was skipped or failed.

## Pre-commit

Pre-commit hooks are configured for Ruff, `ty`, pytest, ESLint, and Prettier. To run all hooks:

```bash
pre-commit run --all-files
```

Use module-specific commands during development; use full pre-commit before broad or cross-module
submissions.
