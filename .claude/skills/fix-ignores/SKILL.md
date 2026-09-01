---
name: fix-ignores
allowed-tools: Bash Read Edit Agent
description: >
  Audit all lint and type suppression comments across the codebase and attempt
  to fix the underlying issues so suppressions can be removed. Covers Python
  (# noqa, # type: ignore, # pyright: ignore) and TypeScript
  (eslint-disable, @ts-ignore, @ts-expect-error). Does NOT auto-commit —
  reports findings and applies fixes to the working tree only.
---

## Goal

Remove as many suppression comments as possible by fixing the underlying issues.
Where fixing is impossible (e.g. untyped third-party library), tighten a bare
suppression to a specific error code. Leave a note for anything requiring manual
judgment. A clean run produces few or no remaining suppressions in first-party
code.

**Never touch generated files** — skip any file with `// eslint-disable` on line 1
or that matches `*.gen.ts`, `*.generated.*`, `alembic/versions/`, or
`node_modules/`.

---

## Step 1 — Collect all suppressions

Run these from the repo root:

```bash
# Python: noqa comments
grep -rn "# noqa" backend/src scripts --include="*.py" | sort

# Python: type: ignore comments
grep -rn "# type: ignore" backend/src scripts --include="*.py" | sort

# Python: pyright: ignore comments
grep -rn "# pyright: ignore" backend/src scripts --include="*.py" | sort

# TypeScript: eslint-disable (skip generated files)
grep -rn "eslint-disable" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -v "\.\(gen\|generated\)\." | sort

# TypeScript: @ts-ignore / @ts-expect-error
grep -rn "@ts-ignore\|@ts-expect-error" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -v "\.\(gen\|generated\)\." | sort
```

Collect all output into a structured list.

---

## Step 2 — Triage each suppression

Spawn a **classify agent** (general-purpose, needs Read and Grep) with the full
list from Step 1 and the following instructions:

```
You are triaging suppression comments in a Python FastAPI + Celery / TypeScript React codebase.

For EVERY suppression comment in the list, read the surrounding file context
(at least 20 lines around the suppressed line) before classifying. Do not
classify from the suppression string alone.

### Classification categories

**FIXABLE** — the underlying issue can be resolved by changing the code:
- Unused variable (noqa: F841, eslint @typescript-eslint/no-unused-vars) — rename
  to `_var` or restructure to avoid creating it
- Unused function argument (noqa: ARG001) — rename to `_arg`, OR if the argument
  is genuinely used (e.g. injected for auth), mark LEGITIMATE instead
- Broad except clause (noqa: BLE001) — narrow to specific exception type if the
  expected error is determinable from context
- `@ts-ignore` with a fixable type error — if the error is a missing property or
  wrong type that can be addressed with a cast or type annotation, mark FIXABLE
- `no-explicit-any` eslint — if the type is knowable from context, mark FIXABLE

**LEGITIMATE** — the suppression is correct and can't be removed without
fighting framework or library constraints:
- `type: ignore[import-untyped]` on a third-party package with no stubs
  (firebase_admin, celery decorators, redis without generics) — these are correct
- `type: ignore[misc]` on `@celery_app.task` or `@limiter.limit` decorators —
  framework decorator typing is impractical to fix
- `pyright: ignore[reportUnnecessaryIsInstance]` on Protocol isinstance checks —
  pyright flags these as unnecessary because Protocols are structural, but the
  runtime check is intentional for safety
- `noqa: B008` on FastAPI `Query(...)` / `Depends(...)` defaults — correct pattern
- `eslint-disable-next-line func-style` in React component files — may reflect a
  team style decision; check if the rule is in eslint config

**TIGHTEN** — suppression is legitimate but uses a bare form that should be
narrowed to a specific error code:
- `# type: ignore` without a bracketed code → identify the error code and add it
- `# noqa` without a code → identify the rule and add it
- `/* eslint-disable */` without a rule (on non-generated files) → add specific rule
- `// eslint-disable` without a rule → add specific rule

**INVESTIGATE** — context is ambiguous; mark for manual review.

For each suppression return:
- file:line
- suppression text
- category: FIXABLE / LEGITIMATE / TIGHTEN / INVESTIGATE
- one-line reason
- proposed change (for FIXABLE and TIGHTEN)
```

Wait for the classify agent to return before continuing.

---

## Step 3 — Apply fixes

Work through the classify agent's findings:

### 3a. FIXABLE suppressions

For each FIXABLE suppression:
1. Read the relevant file section.
2. Apply the fix with Edit — change the code to remove the need for the suppression,
   then delete the suppression comment.
3. After editing, verify no new errors are introduced:
   - Python: `uv run --project backend ruff check <file>` and
     `uv run --project backend pyright <file>`
   - TypeScript: `cd frontend/web && npx tsc --noEmit 2>&1 | grep <file>`

If a fix would be a significant refactor (changing function signatures, altering
call sites across multiple files), do NOT apply it silently — add it to the
INVESTIGATE list with a note explaining the scope.

### 3b. TIGHTEN suppressions

For each TIGHTEN suppression:
1. Read the file. Determine the specific error code (run the linter/typechecker
   without the suppression to see the exact code if uncertain).
2. Edit the suppression comment to include the code.
   - `# type: ignore` → `# type: ignore[<code>]`
   - `# noqa` → `# noqa: <CODE>`
   - `/* eslint-disable */` → `/* eslint-disable <rule> */`
3. No verification run needed for pure comment edits.

### 3c. LEGITIMATE and INVESTIGATE

Do not modify these. Collect them for the final report.

---

## Step 4 — Run QA verification

After all edits:

```bash
# Backend lint + typecheck
cd backend && uv run ruff check src/ && uv run pyright

# Frontend typecheck
cd frontend/web && npx tsc --noEmit
```

If any new errors appear (i.e. errors that were not present before the skill ran),
revert the relevant edit with Edit (restore the original suppression comment) and
move that item to INVESTIGATE.

---

## Step 5 — Report

Print a summary table:

| File | Line | Suppression | Category | Action Taken |
|------|------|-------------|----------|--------------|
| backend/src/.../file.py | 21 | `# type: ignore[type-arg]` | LEGITIMATE | No change |
| backend/src/.../auth.py | 48 | `# type: ignore[misc]` | LEGITIMATE | No change |
| frontend/web/src/.../Button.tsx | 21 | `// eslint-disable-next-line func-style` | INVESTIGATE | Needs manual review |
| ... | ... | ... | ... | ... |

Then print three sections:

### Fixed (N)
List each suppression that was removed, with the code change made.

### Tightened (N)
List each bare suppression that now has a specific error code.

### Remaining — Legitimate (N)
List suppressions that are correct as-is and why.

### Remaining — Investigate (N)
List suppressions that need manual judgment, with the reason.

Close with: "No commits were made. Run `qa` before pushing."
