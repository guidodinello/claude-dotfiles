---
name: configure-dependency
description: Fetch official docs and configure a new dependency correctly from the start. Use when adding a new package, service, or external integration to the project. Trigger phrases: "add X", "integrate X", "configure X", "set up X".
allowed-tools: WebFetch WebSearch Read Bash
---

# Configure Dependency Skill

Before writing any integration code, fetch the official documentation for the dependency so configuration is done correctly from the start. Misconfigurations are the hardest bugs to debug — this skill prevents them.

> **Adapt for your project**: Step 4 below hard-codes paths and conventions
> (`backend/src/fitted_backend/...`, the `FITTED__<GROUP>__<KEY>` env var
> prefix) from the project this skill originated in. Replace them with your
> project's actual config module path and env var convention.

## Instructions

The user provides a dependency name as an argument (e.g. `/configure-dependency celery`). If no name is given, ask before continuing.

### Step 1 — Identify the dependency

Determine:
- The canonical package or service name (e.g. `celery`, `redis`, `alembic`)
- The version currently pinned in the project (check `backend/pyproject.toml`, `docker/docker-compose.yml`, or wherever it's declared). If not yet added, note that it needs to be pinned after this step.
- Which layer it lives in: Python package, Docker service, external API, or OS-level tool.

### Step 2 — Fetch the official documentation

Use WebFetch or WebSearch to retrieve the official setup/configuration guide for this dependency. Prefer:
1. The official docs site (e.g. `docs.celeryq.dev`, `redis.io/docs`)
2. The PyPI or npm page if no dedicated docs site exists
3. The GitHub README as a last resort

Focus on:
- **Installation** — any extras or optional dependencies needed (e.g. `celery[redis]`)
- **Configuration options** — required vs. optional settings, their defaults, and gotchas
- **Framework integration** — if the dependency integrates with FastAPI, SQLAlchemy, or another stack component already in use, look for that specific guide
- **Version-specific notes** — check if the version pinned has known breaking changes or migration notes from the previous major

### Step 3 — Summarize findings before writing code

Before touching any file, present a short summary:
- What the dependency does and where it fits in the Fitted stack
- Required configuration (env vars, init calls, connection params)
- Any gotchas or common mistakes found in the docs
- Recommended version to pin (if not already pinned)

Ask the user to confirm the approach before proceeding to Step 4.

### Step 4 — Implement the configuration

Apply the configuration following the patterns established in the codebase:
- Settings go in `backend/src/fitted_backend/core/config.py` as a nested `Settings` subclass (e.g. `CelerySettings`)
- Env vars use the `FITTED__<GROUP>__<KEY>` prefix convention (see existing config for examples)
- Add the package to `backend/pyproject.toml` under `[project.dependencies]` via `uv add <package>`
- If it's a Docker service, add it to `docker/docker-compose.yml` and `docker/docker-compose.dev.yml`

### Step 5 — Verify

Run the relevant checks to confirm the dependency is wired up correctly:
- `cd backend && uv run python -c "import <package>"` to confirm the install
- If it has a connection (DB, broker, cache), add a health-check call or confirm the existing `/health` endpoint covers it
- Run `cd backend && uv run pyright` to confirm no type errors were introduced

### Step 6 — Confirm and summarize

Report:
- What was installed and where it's configured
- Any env vars the user needs to add to `.env`
- Any follow-up steps (e.g. running a migration, setting a secret in prod)
