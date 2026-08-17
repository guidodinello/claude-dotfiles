---
paths:
  - ".github/workflows/**"
  - "**/.github/workflows/**"
---

<!-- Code examples and table rows can't be rewrapped without breaking them;
     prose is held to 80 columns. This directive travels with the file so it
     lints clean in any repo that vendors it. Claude Code strips block HTML
     comments before injection, so this costs no context. -->
<!-- markdownlint-configure-file {
  "MD013": { "code_blocks": false, "tables": false }
} -->

# CI — Agent Authoring Guidelines

Guidelines for writing and modifying GitHub Actions workflows
(`.github/workflows/`), and the reasoning behind them, so they can be applied
consistently as a pipeline grows.

The self-hosted-runner section applies only if you actually use one — check your
workflow's `runs-on:` before assuming it does. Everything else is
runner-agnostic.

---

## Philosophy

- **If the runner is self-hosted, it is not ephemeral.** On a self-hosted runner
  (`runs-on: [self-hosted, linux, x64]`) rather than a GitHub-hosted throwaway
  VM, anything that binds a host port, writes to a host path, or leaves a
  process running can collide with a developer's local `docker compose up`, a
  previous stuck job, or another concurrent job on the same machine. Assume
  shared, persistent state — GitHub-hosted-runner habits (hardcoded ports, "the
  VM is thrown away after") don't hold. On GitHub-hosted runners these concerns
  don't apply; the rest of this file still does.
- **Fail loudly, gate explicitly.** A job that silently skips or a summary gate
  that doesn't actually check its dependencies' results is worse than a red X.
- **Only run what changed.** Independent pipelines (e.g. backend and frontend)
  shouldn't pay for or block on a job whose inputs didn't change.
- **Least privilege by default.** A workflow file should state what its
  `GITHUB_TOKEN` can do, not silently inherit whatever the repo/org default
  scope happens to be.

---

## Least-privilege permissions

Add an explicit `permissions:` block to every workflow. Without one, every job
runs with the repo/org default `GITHUB_TOKEN` scope — often broader read/write
access than anything in the file actually uses, and that default can change
out from under you if the org setting changes later.

Set the workflow-level default to the narrowest shape most jobs need
(`contents: read` covers checkout + run-tools-and-exit, which is most CI),
then override per-job only where something genuinely needs more:

```yaml
# Bad — no permissions block; every job gets the repo's default GITHUB_TOKEN
# scope, whatever that happens to be
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

# Good — explicit, narrowest-common-denominator default; override per job
name: CI
on: [push, pull_request]
permissions:
  contents: read
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write   # only this job pushes an image
    steps: [...]
```

**A job-level `permissions:` replaces the workflow-level default entirely for
that job — it does not add to it.** Copy the base entries (`contents: read`)
into any job override that also needs something extra; don't rely on them
being inherited alongside it.

| Job does | Needs |
|---|---|
| Checkout + run linters/tests, nothing else | `contents: read` |
| Push a Docker image or package | `packages: write` |
| Merge, comment on, or push to a PR | `pull-requests: write` (+ `contents: write` to merge) |
| Auth via OIDC to a third-party action (e.g. `anthropics/claude-code-action`) | `id-token: write` |
| Pure SSH/external deploy — no GitHub API calls at all | nothing; `permissions: {}` makes that explicit |

A custom PAT passed via `secrets.SOME_PAT` (not `secrets.GITHUB_TOKEN`) is
unaffected by this block entirely — its scope is whatever was granted when
the token was created, configured outside the workflow file.

---

## Self-hosted runner port collisions

*This whole section applies only to jobs whose `runs-on:` is a self-hosted
runner.*

### Never hardcode a service container's host port

A `services:` container's `ports: - 5432:5432` binds port 5432 on the runner
host itself. When the runner is a persistent machine (not a disposable
GitHub-hosted VM), this clashes with anything else already listening there —
most commonly a developer's local `docker compose up` (postgres/redis on the
same box) or a concurrently running CI job.

```yaml
# Bad — binds host port 5432; collides with local dev compose or a parallel job
services:
  postgres:
    image: postgres:16
    ports:
      - 5432:5432

# Good — ephemeral host port, assigned by Docker at container start
services:
  postgres:
    image: postgres:16
    ports:
      - 5432
```

This applies to every `services:` container in a self-hosted job — not just
postgres/redis. Any fixed `host:container` port mapping is a latent collision.

### Resolve the assigned port in a step, not job-level `env`

The ephemeral port GitHub Actions actually assigned is only available via the
`job` context (`job.services.<id>.ports['<container_port>']`) — and the `job`
context is **not populated when job-level `env:` is evaluated**. Referencing it
there silently resolves to empty.

```yaml
# Bad — job.services isn't available yet; DATABASE_PORT ends up empty
env:
  DATABASE_PORT: ${{ job.services.postgres.ports['5432'] }}

# Good — resolve in an early step via $GITHUB_ENV, after job.services exists
steps:
  - name: Resolve service ports
    run: |
      echo "DATABASE_PORT=${{ job.services.postgres.ports['5432'] }}" >> "$GITHUB_ENV"
      echo "REDIS_URL=redis://localhost:${{ job.services.redis.ports['6379'] }}/0" >> "$GITHUB_ENV"
```

Put this step immediately after checkout, before any step that needs the
resolved value. Every later step (and job-level `env:` entries that don't depend
on the port) can stay as-is.

This failure mode is quiet: the expression resolves to an empty string rather
than erroring, so the job runs and fails later with a confusing connection error
— or passes against the wrong database. Nothing in the logs points at the `env:`
block. Review for it explicitly; CI will not flag it.

---

## Path filtering

Use `dorny/paths-filter` behind a `changes` job so backend and frontend
pipelines only run when their own tree changed:

```yaml
changes:
  outputs:
    backend: ${{ steps.filter.outputs.backend }}
    frontend: ${{ steps.filter.outputs.frontend }}
  steps:
    - uses: dorny/paths-filter@v4
      id: filter
      with:
        filters: |
          backend:
            - 'backend/**'
            - '.github/workflows/ci.yml'
          frontend:
            - 'frontend/**'
            - '.github/workflows/ci.yml'
```

Every downstream job gates on it: `needs: changes` + `if:
needs.changes.outputs.backend == 'true'`. Always include the workflow file
itself (`.github/workflows/ci.yml`) in each filter's path list — a workflow
change should re-run everything it affects, not be invisible to path filtering.

---

## Summary gates

A summary gate job exists purely so branch protection can require one check
instead of enumerating every job. It must use `if: always()` and explicitly scan
`needs.*.result` — without `always()`, the gate job is skipped (not failed) the
moment any dependency fails, which branch protection treats as "no status," not
"blocked."

```yaml
backend-gate:
  needs: [lint, typecheck, test-unit, test-integration]
  if: always()
  steps:
    - name: Check results
      run: |
        results=(${{ join(needs.*.result, ' ') }})
        for r in "${results[@]}"; do
          if [[ "$r" == "failure" || "$r" == "cancelled" ]]; then
            exit 1
          fi
        done
```

When adding a new job to a pipeline, add it to the matching summary gate's
`needs:` list too — a job left out of the gate can fail without blocking the
merge.

---

## Quick reference checklist

When authoring or reviewing a workflow file:

- [ ] Workflow has an explicit `permissions:` block (no reliance on the repo/
  org default)
- [ ] Any job overriding `permissions:` repeats the base entries it still
  needs — a job-level block replaces the default, it doesn't add to it
- [ ] On self-hosted runners, no service container uses a hardcoded
  `host:container` port
      mapping — use the ephemeral form (`- 5432`, not `- 5432:5432`)
- [ ] Any value derived from `job.services.<id>.ports[...]` is resolved in a
  step via
      `$GITHUB_ENV`, never referenced directly in job-level `env:`
- [ ] New job is gated behind the `changes` job with the right `if:
  needs.changes.outputs.*`
- [ ] New job's path is listed in the relevant `paths-filter` filter, and the
  workflow file
      itself is included in that filter's path list
- [ ] New job is added to the matching summary gate's `needs:` list
- [ ] Summary/gate jobs use `if: always()` and explicitly check `needs.*.result`
