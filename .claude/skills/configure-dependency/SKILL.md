---
name: configure-dependency
description: 'Trigger: configure a new dependency, integrate a third-party service or SDK, add a package that needs config or env vars. Not for adding files, skills or features. Fetches the official docs first, then wires it up.'
allowed-tools: WebFetch WebSearch Read Bash
---

# Configure Dependency Skill

Before writing any integration code, fetch the official documentation for the dependency so configuration is done correctly from the start. Misconfigurations are the hardest bugs to debug — this skill prevents them.

> **Discover, don't assume**: Step 4 follows the project's own config module and
> env var scheme. Find them first (`grep -rn 'BaseSettings\|process.env' ...`,
> existing `.env.example`) and copy what is there.

## Instructions

The user provides a dependency name as an argument (e.g. `/configure-dependency celery`). If no name is given, ask before continuing.

### Step 1 — Identify the dependency

Determine:

- The canonical package or service name (e.g. `celery`, `redis`, `alembic`)
- The version currently pinned in the project (check `pyproject.toml`, `package.json`, the docker-compose files, or wherever it's declared). If not yet added, note that it needs to be pinned after this step.
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

- What the dependency does and where it fits in the project's stack
- Required configuration (env vars, init calls, connection params)
- Any gotchas or common mistakes found in the docs
- Recommended version to pin (if not already pinned)

Ask the user to confirm the approach before proceeding to Step 4.

### Step 4 — Implement the configuration

Apply the configuration following the patterns established in the codebase:

- Settings go in the project's existing settings module, following its pattern (for example a nested settings class per dependency)
- Env vars copy the existing env-var scheme (for example `<APP>__<GROUP>__<KEY>`); look at the current config and `.env.example`
- Add the package through the project's package manager (for example `uv add <package>` into `pyproject.toml`, or `npm install`)
- If it's a Docker service, add it to the project's compose files

### Step 5 — Verify

Run the relevant checks to confirm the dependency is wired up correctly:

- The project's import or install check (for example `uv run python -c "import <package>"`) to confirm the install
- If it has a connection (DB, broker, cache), add a health-check call or confirm the existing health endpoint covers it
- Run the project's type checker to confirm no type errors were introduced

### Step 6 — Confirm and summarize

Report:

- What was installed and where it's configured
- Any env vars the user needs to add to `.env`
- Any follow-up steps (e.g. running a migration, setting a secret in prod)
