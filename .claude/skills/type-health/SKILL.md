---
name: type-health
allowed-tools: Bash Read Edit Agent
description: >
  Audit and improve type coverage across the codebase on demand — Python
  backend (Pydantic at every IO boundary) and TypeScript frontend (Zod-first
  types). Use after a big feature lands or as a periodic health check.
  Does NOT auto-commit — reports findings and applies fixes to the working
  tree only.
---

## Goal

Tighten types where it prevents real bugs, not to maximize annotation count.
Two project conventions anchor every finding:

- **Backend — Pydantic at every IO boundary.** Data entering or leaving the
  system (API request/response, DB rows, external service payloads) should have
  a Pydantic model. Pydantic models *are* the types in Python (no `z.infer`
  step needed), so one definition gives runtime validation + static types.
  Replace `dict[str, Any]` with a named model wherever the shape is known.
- **Frontend — Zod-first types.** Define a Zod schema at every API boundary and
  derive the TypeScript type via `z.infer<>`. Never hand-write types that
  duplicate schema information — they drift. Never `as`-cast at IO boundaries —
  use Zod `.parse()`/`.safeParse()` instead. (The `apiGet`/`privateApiGet`
  helpers already embed this pattern.)

A well-typed codebase should produce few findings.

## References

| File | Contents | Read it in |
|------|----------|------------|
| [`references/type-checks.md`](references/type-checks.md) | Every grep, the checker-config table, classification rules, quick checklist | Steps 1, 1b, 2 |
| [`references/type-philosophy.md`](references/type-philosophy.md) | Heuristics H1–H11 as ideas, plus concepts we document but deliberately do not check | Step 2 |

**Never touch generated files** — skip `*.gen.ts`, `*.generated.*`,
`routeTree.gen.ts`, `alembic/versions/`, and `node_modules/`.

---

## Step 0 — Scope

Default scope is `backend/src`, `scripts/`, and `frontend/web/src`. If the user
passed a path or module as an argument, narrow to it. Note the scope in the
final report.

**Tests are out of scope by default.** `frontend/web/src` contains
`src/__tests__`, which dominates several scans (on the first run: 13 of 20
`noUncheckedIndexedAccess` errors and 58 of the 65 filtered `as` hits).
Loose types in a test are usually deliberate — fakes, partial fixtures,
deliberate bad input. Exclude `__tests__` and `tests/` unless the user asks for
them, and say which policy you applied in the report.

---

## Step 1 — Mechanical scan

Run the Python and TypeScript scans from
[`references/type-checks.md`](references/type-checks.md) §1–2 verbatim, from
the repo root. Collect all hits into a structured list.

---

## Step 1b — Checker-configuration audit

Skip only if Step 0 narrowed the scope to a single module.

Follow [`references/type-checks.md`](references/type-checks.md) §3: read
`backend/pyproject.toml` `[tool.pyright]` and
`frontend/web/tsconfig.app.json`, compare against the recommended-flag table,
and **measure** each missing flag by running the checker with it enabled. Check
the `exclude` list too — an excluded directory is exempt from every rule at once.

Report measured counts, never reputations. Every config finding is
INVESTIGATE — this skill never flips a flag.

---

## Step 2 — Classify (agent)

Spawn a **single classify agent** (general-purpose, needs Read and Bash) with
the Step 1 grep output and these instructions:

```
You are classifying type-coverage findings in a Python FastAPI + Celery /
TypeScript React codebase. The backend convention is Pydantic at every IO
boundary; the frontend convention is Zod-first types (schema at the boundary,
type via z.infer).

Read BOTH of these first, in full:
  .claude/skills/type-health/references/type-checks.md    (§4 classification rules)
  .claude/skills/type-health/references/type-philosophy.md (H1–H11, the reasoning)

For EVERY hit, read ~20 lines of context around the line in the actual file
before classifying. Do not classify from the grep string alone.

Classify each into FIX / LEGITIMATE / INVESTIGATE per type-checks.md §4.
Use the philosophy doc to judge the cases the rules don't settle — that is
what it is for. Never open a finding against anything in its "Concepts we
document but do not check" section.

For each finding return:
- file:line
- pattern matched
- heuristic (H1–H11)
- category: FIX / LEGITIMATE / INVESTIGATE
- one-line reason citing what you read in the file
- proposed change (for FIX)

Be conservative — when in doubt, mark INVESTIGATE, not FIX.
```

Wait for the classify agent to return before continuing.

---

## Step 3 — Apply fixes

Work through FIX findings in priority order (High-priority heuristics first —
see the Priority Summary in `references/type-philosophy.md`):

1. Read the relevant file section.
2. Apply the fix with Edit. For new Pydantic models / Zod schemas, place them
   where the project convention puts boundary types (next to the existing
   schemas for that module — check neighboring files).
3. After each file's edits, verify no new errors:
   - Python: `uv run --project backend ruff check <file>` and
     `uv run --project backend pyright <file>`
   - TypeScript: `cd frontend/web && npx tsc --noEmit 2>&1 | grep <file>`

If a fix would ripple across multiple files (shared signature change, new
schema consumed by several modules), do NOT apply it silently — move it to
INVESTIGATE with a note on scope. Do not modify LEGITIMATE findings.

---

## Step 4 — QA verification

After all edits:

```bash
# Backend lint + typecheck
(cd backend && uv run ruff check src/ && uv run pyright)

# Frontend typecheck
(cd frontend/web && npx tsc --noEmit)
```

**Run the test suites too if any fix touched a Pydantic model or Zod schema.**
Static checks structurally cannot verify those: Pydantic `Field` constraints and
Zod refinements are *runtime* validation, and in this repo the constrained types
mostly live under `src/fitted_backend/ml`, which pyright excludes. A green
pyright says nothing about whether an H10 constraint just started rejecting real
data.

```bash
(cd backend && uv run pytest -q -m "not integration")
(cd frontend/web && npx vitest run)
```

State in the report which suites ran and which did not (integration tests need
Postgres; say so rather than implying full coverage).

If any new error appears that was not present before the skill ran, revert the
responsible edit and move that finding to INVESTIGATE.

If Step 1b temporarily edited `backend/pyproject.toml` to measure a pyright
flag, confirm it was restored: `git status --porcelain backend/pyproject.toml`
must be empty.

---

## Step 5 — Report

Print a summary table:

| File | Line | Pattern | Heuristic | Category | Action |
|------|------|---------|-----------|----------|--------|
| ... | ... | ... | H7d | FIX | Fixed |

Then four sections:

### Fixed (N)

Each tightened type, with the change made.

### Checker configuration (N)

Each missing strictness flag, with its measured error count and where those
errors land (`src/` vs tests). No action taken.

### Remaining — Legitimate (N)

Loose types that are correct as-is, and why.

### Remaining — Investigate (N)

Findings needing manual judgment or a design decision, with scope notes.

Close with: "No commits were made. Run `qa` before pushing."
