---
name: api-gap-audit
allowed-tools: Bash Read Write Grep Glob
description: >
  Detect backend API endpoints that have no frontend integration, and vice-versa.
  Greps all route definitions in the backend and all API call sites in the frontend,
  diffs them, and classifies each gap. Does NOT modify code — reports only.
---

## Goal

Find backend endpoints missing from the frontend (real integration gaps) and
frontend callers hitting paths the backend doesn't serve. Run after adding new
routes, before a release, or periodically to catch drift between the two layers.

---

## Step 1 — Extract backend routes

From the repo root, run:

```bash
# Find all route files and extract method + path for each endpoint
grep -rn '^\s*@router\.\(get\|post\|put\|patch\|delete\)(' \
  backend/src/fitted_backend/api/routes/ --include="*.py"
```

Also check which `APIRouter` prefixes exist to resolve full paths:

```bash
grep -rn 'APIRouter(prefix=' backend/src/fitted_backend/api/routes/ --include="*.py"
```

Build a list of full endpoint paths (prefix + route path).

---

## Step 2 — Extract frontend call sites

From the repo root, run:

```bash
# Find all explicit API path references in the frontend
grep -rn "'/[a-z]" frontend/web/src/api/ --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u

grep -rn "'/[a-z]" frontend/web/src/lib/queries/ --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u

grep -rn "'/[a-z]" frontend/web/src/lib/onboarding.ts frontend/web/src/store/ --include="*.ts" \
  | grep -v "__tests__" \
  | grep -o "'/[^']*'" | sort -u
```

Also check for any API URLs constructed dynamically:

```bash
grep -rn 'apiGet\|apiPost\|apiDelete\|privateApiGet\|privateApiPost\|privateApi\.\|publicApi\.' \
  frontend/web/src/ --include="*.ts" | grep -v "__tests__" | grep -v ".test."
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
