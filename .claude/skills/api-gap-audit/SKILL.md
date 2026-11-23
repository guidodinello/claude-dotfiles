---
name: api-gap-audit
allowed-tools: Bash Read Write Grep Glob
description: 'Find backend endpoints with no frontend caller, and frontend calls the backend does not serve.'
---

## Goal

Find backend endpoints missing from the frontend (real integration gaps) and
frontend callers hitting paths the backend doesn't serve. Run after adding new
routes, before a release, or periodically to catch drift between the two layers.

---

## Step 0 — Discover source roots

Do not assume a layout. Before running any command below, find the roots and
use them in place of the `<placeholders>`:

- `<backend-project>`: a directory with a `pyproject.toml` (`git ls-files '*pyproject.toml'`). `<backend-src>` is its source root (`src/` or the package directory) and `<backend-pkg>` the importable package under it.
- `<routes-dir>`: the directory (or directories) under `<backend-pkg>` that define the route handlers (`grep -rln 'APIRouter\|@router\.' <backend-src>`).
- `<frontend-project>`: a directory with a `package.json` (`git ls-files '*package.json'`, ignoring `node_modules`) whose `src/` holds the UI code. `<frontend-src>` is that `src/`.
- `<api-call-dirs>`: the directories and files under `<frontend-src>` that make API calls (`grep -rln 'fetch(\|axios\|apiGet\|apiPost' <frontend-src>`).

If a root this skill needs cannot be found, stop and ask the user. An empty grep
result is never a clean audit: confirm each root exists and holds files before
reporting zero findings.

---

## Step 1 — Extract backend routes

From the repo root, run:

```bash
# Find all route files and extract method + path for each endpoint
grep -rn '^\s*@router\.\(get\|post\|put\|patch\|delete\)(' \
  <routes-dir>/ --include="*.py"
```

Also check which `APIRouter` prefixes exist to resolve full paths:

```bash
grep -rn 'APIRouter(prefix=' <routes-dir>/ --include="*.py"
```

Build a list of full endpoint paths (prefix + route path).

---

## Step 2 — Extract frontend call sites

From the repo root, run:

```bash
# Find all explicit API path references in the frontend
grep -rn "'/[a-z]" <api-call-dirs> --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u

grep -rn "'/[a-z]" <api-call-dirs> --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u

grep -rn "'/[a-z]" <api-call-dirs> --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u
```

Also check for any API URLs constructed dynamically:

```bash
grep -rn 'apiGet\|apiPost\|apiDelete\|privateApiGet\|privateApiPost\|privateApi\.\|publicApi\.' \
  <frontend-src>/ --include="*.ts" | grep -v "__tests__" | grep -v ".test."
```

---

## Step 3 — Diff and classify

Compare the two lists. For each backend endpoint with no frontend caller, classify:

| Category | Meaning | Action |
|----------|---------|--------|
| **real gap** | Endpoint serves a user-facing feature the FE should call but doesn't | File an issue |
| **infra** | Health checks, admin-only, or internal ops endpoints | No action |
| **mobile-only** | Endpoint exists for the mobile app (e.g. `/users/me/fcm-token`) | No action unless web needs parity |
| **dev tool** | Endpoint for scripts, simulators, or debugging only | Mark in results, no issue |
| **duplicate** | Multiple endpoints for the same thing (e.g. GET + POST /questions) | Consider consolidating |

For each pair, also flag frontend callers hitting paths the backend doesn't serve.

---

## Step 4 — Report

Return a markdown table:

| Endpoint | Method | FE caller? | Classification | Notes |
|----------|--------|------------|---------------|-------|
| `/auth/login` | POST | ✅ `api/auth.ts:45` | integrated | — |
| `/auth/logout` | POST | ❌ | real gap | File issue |
| `/auth/verify-email` | GET | ❌ | real gap | File issue |
| `/onboarding/questions` | POST | ❌ | dev tool | Simulator only — consider removing |
| `/users/me/fcm-token` | PATCH | ❌ | mobile-only | FCM push — no web action needed |
| `/health` | GET | ❌ | infra | Health check — no action |

For each **real gap**, create an issue file in `docs/process/issues/` (next sequential number) using the issue template. Group small gaps into a single issue if they're closely related (e.g. "Add timezone + gender preferences to YouScreen").

Close by telling the user: no code was modified, and the issues are ready to pick up.
