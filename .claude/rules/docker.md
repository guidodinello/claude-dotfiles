---
paths:
  - "**/Dockerfile*"
  - "**/*.dockerfile"
  - "**/docker-compose*.yml"
  - "**/docker-compose*.yaml"
  - "**/.dockerignore"
---

# Docker — Agent Authoring Guidelines

Guidelines for writing Dockerfiles and Compose configurations, and the reasoning behind
them, so they can be applied consistently when new services are added.

Examples use Python + `uv`, since that's what most services here run, but the rules —
pinning, multi-stage layering, cache ordering, non-root, and every Compose pattern below
— are language-agnostic. Substitute your own toolchain's lockfile and install command.

---

## Philosophy

- **Build artifacts, not environments** — a Docker image is a reproducible, versioned
  artifact. Treat it with the same rigour as source code: pin versions, commit lockfiles,
  and make builds deterministic.
- **Smallest possible attack surface** — strip everything that isn't needed at runtime.
  Build tools, test dependencies, and package managers belong in the build stage, not
  the final image.
- **Separate dev from prod** — development images optimise for fast iteration (volume
  mounts, hot reload). Production images optimise for security and size. Never use a dev
  image in production.
- **Fail loudly** — a healthcheck that lies, a CMD that hides errors, or a volume mount
  that silently shadows the wrong directory are worse than a build failure.

---

## Image versioning

### Pin to minor version at minimum

Never use `:latest` or an unqualified major tag for base images — they can change on any
registry push and silently break builds.

```dockerfile
# Bad
FROM python:latest
FROM python:3

# Acceptable — pinned to minor version; patch updates are usually safe
FROM python:3.13-slim

# Best for production — pinned to digest; byte-for-byte reproducible
FROM python:3.13.3-slim@sha256:<hash>
```

### Pin the uv binary version

The `ghcr.io/astral-sh/uv` image follows the same rule. Use a specific version tag:

```dockerfile
# Bad
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Good
COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/
```

Pin a real release rather than the `<version>` placeholder shown here — it is left
abstract deliberately, so this guideline can't teach a stale number. When upgrading uv,
update the pin in every Dockerfile that uses it and commit together with any `uv.lock`
changes.

---

## Multi-stage builds

Use multi-stage builds for all production images. The builder stage installs everything
needed to compile and install dependencies; the final stage receives only the artifacts.

```dockerfile
# Stage 1 — builder: uv, build tools, compile bytecode
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --frozen --no-dev


# Stage 2 — final: no uv, no build tools, just the venv and source
FROM python:3.13-slim AS final

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app /app
USER appuser

CMD ["myapp", "start"]
```

**Why two `uv sync` calls?** The first installs deps without the project source, creating
a cacheable layer. The second adds the project itself. When only `src/` changes, Docker
reuses the expensive dependency layer.

---

## Layer cache ordering

Instructions are cached top-to-bottom. Place stable operations first; volatile ones last.

```dockerfile
# Bad — invalidates dep cache on every source change
COPY . .
RUN uv sync --frozen

# Good — dep install is cached until pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN uv sync --frozen --no-dev
```

General ordering rule for a service (Python/uv shown; the shape is the same for
`package.json`/lockfile/install or any other toolchain):

1. Base image + package-manager binary
2. ENV vars (rarely change)
3. System packages (`apt-get install ...`)
4. Dependency files (`pyproject.toml`, `uv.lock`)
5. Dependency install (`uv sync`)
6. Application source (`COPY src/ ./src/`)
7. Project install / final sync

---

## uv-specific patterns

### Environment variables

Always set these in the builder stage:

| Variable | Value | Why |
|----------|-------|-----|
| `UV_COMPILE_BYTECODE` | `1` | Compiles `.pyc` at build time; removes startup delay from bytecode compilation |
| `UV_LINK_MODE` | `copy` | Cache mounts can span filesystems; hard links fail across device boundaries |

In the final stage, set `PYTHONDONTWRITEBYTECODE=1` — bytecode was already compiled in
the builder, so runtime writes are wasted I/O.

### Always use `--frozen`

In any `RUN uv sync` or `RUN uv pip install` inside a Dockerfile, pass `--frozen`. This
ensures the lockfile is the authoritative source of versions and the build fails loudly
if the lock is out of date rather than silently upgrading.

The principle generalizes — an image build is exactly where you want the lockfile treated
as authoritative. The equivalent in the Node ecosystem is `npm ci` (not `npm install`) or
`pnpm install --frozen-lockfile`. Check your own package manager's flag rather than
assuming; the failure mode of getting it wrong is a silent version drift between the
lockfile and the image.

```dockerfile
# Bad — may upgrade packages silently
RUN uv sync

# Good — fails if lockfile is stale
RUN uv sync --frozen --no-dev
```

### Cache mounts (CI / repeat builds)

Use `--mount=type=cache` to persist the uv download cache across builds on the same
host. This is especially valuable in CI with a warm cache:

```dockerfile
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev
```

Note: cache mounts are silently ignored if BuildKit is unavailable, so this is always
safe to include.

### No uv in the final stage (production)

The runtime image should not include uv. Commands like `uv run` won't work — the final
CMD should invoke the entry point directly:

```dockerfile
# Bad — brings uv into the final image
CMD ["uv", "run", "myapp", "start"]

# Good — uses the venv on PATH directly
CMD ["myapp", "start"]
```

---

## Non-root user

Always run the application as a non-root user in production images.

```dockerfile
# Create the user early (before COPY --chown) so the UID is available
RUN useradd --create-home appuser

COPY --from=builder --chown=appuser:appuser /app /app

USER appuser   # switch after COPY; all runtime processes run as appuser
```

Never switch back to root after the `USER` instruction. If a `RUN` command after `USER`
needs elevated permissions, restructure the stage so it runs before the switch.

---

## .dockerignore

Every build context directory must have a `.dockerignore`. Without it, Docker sends
`.git`, caches, `.env` files, and the entire virtual environment to the daemon on every
build — bloating context size and risking leaking secrets.

```text
# .dockerignore — at the root of the build context
.git
.venv
.env
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.coverage
htmlcov/
*.egg-info
dist/
build/
*.log
```

Rule of thumb: if the file doesn't need to be in the image, it shouldn't be in the
context. Start restrictive and add back only what's needed.

---

## Dev image pattern

Dev images mount source at runtime and do not need a multi-stage build. They optimise
for rebuild speed: run the expensive dep install once, then live-reload from the volume.

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:<version> /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project

# Source is volume-mounted at runtime — no COPY src/ needed
CMD ["uv", "run", "myapp", "dev"]
```

Key differences from the production image:

- No `UV_COMPILE_BYTECODE` (adds build time for no benefit in dev)
- `uv.lock*` (asterisk) — tolerates a missing lockfile on first run
- No `USER appuser` — volume mount permissions are simpler as root in dev
- `uv run myapp dev` instead of `myapp start` — enables hot reload

---

## Docker Compose patterns

### YAML anchors for shared config

When multiple services share the same image, env vars, and volumes (e.g. an API, a
background worker, and a scheduler), use a YAML anchor to avoid repetition:

```yaml
x-app-base: &app-base
  build:
    context: .
    dockerfile: docker/Dockerfile.dev
  environment: &app-env
    DATABASE_HOST: postgres
    REDIS_URL: redis://redis:6379/0
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  api:
    <<: *app-base
    ports:
      - "8000:8000"

  worker:
    <<: *app-base
    command: ["uv", "run", "myapp", "worker"]

  scheduler:
    <<: *app-base
    command: ["uv", "run", "myapp", "scheduler"]
```

Keep dev-only keys (bind mounts, exposed ports) out of a shared base anchor if any
service built from that anchor also runs in production — see
[Multi-file merges append lists, they don't replace them](#multi-file-merges-append-lists-they-dont-replace-them)
below for why.

### Multi-file merges append lists, they don't replace them

When stacking Compose files (`-f base.yml -f prod.yml`), most list-valued keys —
`volumes`, `ports`, `expose`, `dns`, `env_file`, `labels` — are **merged/concatenated**,
not replaced. `command` and `entrypoint` are the exception: those fully replace. This
means a dev-only bind mount or port defined in a shared base service (or a base anchor
merged with `<<:`) silently follows that service into every file stacked on top of the
base, including prod, unless the override file explicitly blocks it.

Two shapes this takes, both seen in practice:

- `api`'s `ports: ["8000:8000"]` in the base file merges with prod's
  `["127.0.0.1:8000:8000"]`, binding both and failing with `bind: address already in
  use` — or worse, succeeding and leaving the service publicly reachable.
- A base anchor's dev hot-reload bind mount (`./src:/app/src`) merges into every prod
  service that uses the anchor, so production serves code from the host filesystem
  instead of the image built by the prod Dockerfile.

Two ways to prevent this — prefer the first, since it removes the footgun structurally
instead of requiring every override site to remember a guard:

1. **Don't put an environment-specific value in a base file/anchor at all — declare it
   explicitly in each overlay that needs it instead.** This covers both "dev-only, prod
   doesn't need it" (move the key to `docker-compose.dev.yml` only) and "both need it,
   but with different values" (e.g. `api`'s `ports:` — remove it from the base file,
   then declare `["8000:8000"]` in `docker-compose.dev.yml` and
   `["127.0.0.1:8000:8000"]` in `docker-compose.prod.yml`, each on its own, nothing to
   merge against). Either way, there's no shared list for Compose to append to.
2. **Only if a value genuinely can't be split this way** (rare — most cases fit #1),
   force a full replace with the `!override` YAML tag and a comment stating what would
   leak without it:

   ```yaml
   ports: !override
     - "127.0.0.1:8000:8000"
   ```

   Treat this as a fallback, not the default tool — it depends on every future editor
   of the base file remembering the override exists, which is the same failure mode
   that caused the bug in the first place.

Either way, verify the result — don't assume the merge behaved as intended:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Read the rendered service definitions for anything dev-only (bind mounts to a host path,
0.0.0.0 port bindings, dev-only sidecar containers) that shouldn't be there. Do this
any time a compose file is added, removed, or has a list-valued key touched in a service
that's shared across environments.

### Defaults in Compose, overrides in `.env`

Bake sensible local dev defaults directly into the Compose file using `${VAR:-default}`
syntax. This makes `docker compose up` work out of the box with zero configuration:

```yaml
environment:
  DATABASE_USER: ${DATABASE_USER:-app}
  DATABASE_PASSWORD: ${DATABASE_PASSWORD:-devpassword}
```

Production secrets go in the deployment platform's secret manager, never in a committed
file.

### Healthchecks on every service

Services that depend on others must declare healthchecks so `depends_on: condition:
service_healthy` actually waits for readiness, not just container start:

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U app -d app"]
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 10s
```

---

## Volumes

Docker has three volume types. Pick the right one for the job — mixing them up is the
most common source of "why did my data disappear?" bugs.

### Named volumes — persistent data

Use named volumes for anything that must survive container restarts and `docker compose
down`. The Docker daemon owns the lifecycle; data is kept until you explicitly remove the
volume.

```yaml
services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data  # named: data persists

volumes:
  postgres_data:  # declare at top level — Docker manages the path
```

Rules:

- Always declare named volumes at the top-level `volumes:` key.
- Give them descriptive names: `postgres_data`, `redis_data`, not `data` or `vol1`.
- `docker compose down` keeps them. `docker compose down -v` removes them — use `-v`
  only when you intend to wipe state (e.g. resetting a local DB).

### Bind mounts — dev source code

Bind mounts map a host path directly into the container. Use them in dev to get hot
reload without rebuilding the image. Never use bind mounts in production images.

```yaml
services:
  api:
    volumes:
      - ./src:/app/src:cached  # bind: host path → container path
```

The `:cached` consistency hint (Docker Desktop on macOS) tells the daemon that the host
is authoritative — reads from the container may be slightly stale but writes are fast.
On Linux it has no effect and can be omitted, but it's harmless.

**Never bind-mount the entire project root** — you'll shadow `.venv`, node_modules, or
build artifacts that live inside the container but not on the host:

```yaml
# Bad — shadows /app/.venv inside the container
volumes:
  - .:/app

# Good — mount only the source tree; deps stay inside the image
volumes:
  - ./src:/app/src:cached
```

### tmpfs — ephemeral scratch space

Use `tmpfs` for data that must not persist and shouldn't touch disk (e.g. test
databases, session stores under test). It lives only in RAM and vanishes when the
container stops.

```yaml
services:
  api-test:
    tmpfs:
      - /tmp
      - /run
```

---

## Networks

### Default network is usually enough

Docker Compose creates a single default network for every project. All services on that
network can reach each other by service name — `postgres`, `redis`, `api` — without any
`networks:` config. Add custom networks only when you have an actual isolation
requirement.

```yaml
# This just works — api can connect to postgres:5432 and redis:6379
services:
  api:
    ...
  postgres:
    ...
  redis:
    ...
# No networks: key needed
```

### Custom networks for explicit isolation

If the project grows to have subsystems that should not talk to each other (e.g. a
frontend container that must not reach the database directly), define named networks and
assign services explicitly:

```yaml
networks:
  backend:    # api ↔ postgres ↔ redis
  frontend:   # nginx ↔ api only

services:
  nginx:
    networks: [frontend]

  api:
    networks: [frontend, backend]  # bridge between the two

  postgres:
    networks: [backend]            # not reachable from nginx

  redis:
    networks: [backend]
```

Only introduce this complexity when you have a concrete reason (security boundary,
port collision, multi-project shared services). Don't add networks speculatively.

### `ports` vs `expose`

| Directive | Effect | Use when |
|-----------|--------|----------|
| `ports: ["8000:8000"]` | Maps host port → container port | You need to reach the service from the host (browser, curl, IDE) |
| `expose: ["5432"]` | Documents the port; no host mapping | Service is internal-only; other containers already reach it by name |

```yaml
services:
  api:
    ports:
      - "8000:8000"    # reachable from host at localhost:8000

  postgres:
    expose:
      - "5432"         # reachable by other containers as postgres:5432; NOT from host
    # If you also need psql from the host: ports: ["5432:5432"]
```

Don't map every service port to the host — it creates unnecessary exposure and port
collision risk. Map only what you actively need during development.

### Service DNS

Within the default (or any shared) network, services resolve each other by their
`services:` key name. Use these DNS names in environment variables, never `localhost` or
hardcoded IPs:

```yaml
# Good
environment:
  DATABASE_HOST: postgres     # resolves to the postgres container
  REDIS_URL: redis://redis:6379/0

# Bad — localhost is the container's own loopback, not another service
environment:
  DATABASE_HOST: localhost
```

---

## Quick reference checklist

When authoring or reviewing a Dockerfile:

- [ ] Base image pinned to minor version (or digest for prod)
- [ ] uv binary pinned to a specific version tag
- [ ] Multi-stage build: builder stage separate from final stage (prod only)
- [ ] Dependencies copied and installed before application source
- [ ] `--frozen` on all `uv sync` / `uv pip install` commands
- [ ] `UV_LINK_MODE=copy` and `UV_COMPILE_BYTECODE=1` set in builder stage
- [ ] Final stage runs as non-root (`USER appuser`)
- [ ] `.dockerignore` present in the build context directory
- [ ] No secrets or `.env` files copied into any image
- [ ] CMD uses the venv entry point directly (prod) or `uv run` (dev)

When authoring or reviewing a Compose file:

- [ ] Persistent data uses named volumes (declared at top-level `volumes:`)
- [ ] Dev source code uses bind mounts scoped to `src/`, not the whole project root
- [ ] `docker compose down -v` documented where appropriate (wipes named volumes)
- [ ] Services use DNS names (`postgres`, `redis`), never `localhost`
- [ ] Only necessary ports mapped to host via `ports:`; internal-only services use `expose:` or nothing
- [ ] Custom networks only if there is an explicit isolation requirement
- [ ] Environment-specific list keys (`volumes`, `ports`, etc.) are declared per-overlay
      (dev value in `docker-compose.dev.yml`, prod value in `docker-compose.prod.yml`),
      not left in a shared base file/anchor with one side overriding — `!override` is a
      fallback for cases where a value truly can't be split this way, not the default
- [ ] Any remaining `!override` usage still has a comment stating what would leak
      without it, and is confirmed by `docker compose ... config` to merge as intended
