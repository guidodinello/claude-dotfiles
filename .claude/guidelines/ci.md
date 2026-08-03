# CI — Agent Authoring Guidelines

Guidelines for writing and modifying GitHub Actions workflows (`.github/workflows/`).
Covers the patterns used in this project and the reasoning behind them so they can be
applied consistently as the pipeline grows.

---

## Philosophy

- **This runner is not ephemeral.** CI runs on a self-hosted runner (`runs-on: [self-hosted,
  linux, x64]`), not GitHub-hosted throwaway VMs. Anything that binds a host port, writes to
  a host path, or leaves a process running can collide with a developer's local `docker
  compose up`, a previous stuck job, or another concurrent job on the same machine. Assume
  shared, persistent state — GitHub-hosted-runner habits (hardcoded ports, "the VM is thrown
  away after") don't hold here.
- **Fail loudly, gate explicitly.** A job that silently skips or a summary gate that doesn't
  actually check its dependencies' results is worse than a red X.
- **Only run what changed.** Backend and frontend pipelines are independent — don't pay for
  or block on a job whose inputs didn't change.

---

## Self-hosted runner port collisions

### Never hardcode a service container's host port

A `services:` container's `ports: - 5432:5432` binds port 5432 on the runner host itself.
Since the runner is a persistent machine (not a disposable GitHub-hosted VM), this clashes
with anything else already listening there — most commonly a developer's local `docker
compose up` (postgres/redis on the same box) or a concurrently running CI job.

```yaml
# Bad — binds host port 5432; collides with local dev compose or a parallel job
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - 5432:5432

# Good — ephemeral host port, assigned by Docker at container start
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports:
      - 5432
```

This applies to every `services:` container in a self-hosted job — not just postgres/redis.
Any fixed `host:container` port mapping is a latent collision.

### Resolve the assigned port in a step, not job-level `env`

The ephemeral port GitHub Actions actually assigned is only available via the `job` context
(`job.services.<id>.ports['<container_port>']`) — and the `job` context is **not populated
when job-level `env:` is evaluated**. Referencing it there silently resolves to empty.

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

Put this step immediately after checkout, before any step that needs the resolved value.
Every later step (and job-level `env:` entries that don't depend on the port) can stay as-is.

This bit us in [PR #294](https://github.com/guidodinello/fitted/pull/294): the first attempt
put the `job.services...` expression directly in job-level `env:`, which silently produced an
empty `DATABASE_PORT`/`REDIS_URL` rather than erroring — caught in review, not by CI failing
loudly.

---

## Path filtering

Use `dorny/paths-filter` behind a `changes` job so backend and frontend pipelines only run
when their own tree changed:

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
            - 'scripts/**'
            - '.github/workflows/ci.yml'
          frontend:
            - 'frontend/web/**'
            - '.github/workflows/ci.yml'
```

Every downstream job gates on it: `needs: changes` + `if: needs.changes.outputs.backend ==
'true'`. Always include the workflow file itself (`.github/workflows/ci.yml`) in each
filter's path list — a workflow change should re-run everything it affects, not be
invisible to path filtering.

---

## Summary gates

`backend-ci` / `frontend-ci` exist purely so branch protection can require one check instead
of enumerating every job. They must use `if: always()` and explicitly scan
`needs.*.result` — without `always()`, the gate job is skipped (not failed) the moment any
dependency fails, which branch protection treats as "no status," not "blocked."

```yaml
backend-ci:
  needs: [lint-python, typecheck-python, test-python-unit, test-python-integration, security-python]
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

When adding a new job to a pipeline (backend or frontend), add it to the matching summary
gate's `needs:` list too — a job left out of the gate can fail without blocking the merge.

---

## Quick reference checklist

When authoring or reviewing a workflow file:

- [ ] No service container uses a hardcoded `host:container` port mapping — use the
      ephemeral form (`- 5432`, not `- 5432:5432`)
- [ ] Any value derived from `job.services.<id>.ports[...]` is resolved in a step via
      `$GITHUB_ENV`, never referenced directly in job-level `env:`
- [ ] New job is gated behind the `changes` job with the right `if: needs.changes.outputs.*`
- [ ] New job's path is listed in the relevant `paths-filter` filter, and the workflow file
      itself is included in that filter's path list
- [ ] New job is added to the matching summary gate's `needs:` list (`backend-ci` /
      `frontend-ci`)
- [ ] Summary/gate jobs use `if: always()` and explicitly check `needs.*.result`
