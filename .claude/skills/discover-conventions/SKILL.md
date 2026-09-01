---
name: discover-conventions
description: >
  Explore the whole codebase (frontend + backend), surface de-facto conventions the
  code follows but that aren't written down, and propose codification — ADR drafts,
  CLAUDE.md additions, and docs/conventions.md index entries. Use when best practices
  feel implicit, after a big feature lands, or before onboarding new contributors.
  Proposes and scaffolds docs/tickets; does NOT refactor application code or auto-commit.
---

# Discover Conventions

Surface the implicit conventions this codebase follows but hasn't yet codified, then
help turn them into ADRs, `CLAUDE.md` rules, and `docs/conventions.md` index entries.

A healthy, well-documented codebase should produce **few new findings** — most
conventions are already documented. The expected output of a run is a short list of
genuine gaps, not an exhaustive catalogue of what already exists.

---

## Phase 1 — Know what's already documented

Before exploring, build an inventory of what's already codified so you don't
re-propose it.

**Read these sources in order:**

1. `docs/conventions.md` — the central index (if it exists). This is your starting set.
2. All ADRs in `docs/process/adr/` — scan titles first via the `README.md`, then read
   any whose title suggests a convention rather than a one-time decision.
3. The 7 `CLAUDE.md` files: root, `backend/`, `frontend/web/`, `frontend/mobile/`,
   `scripts/`, `docker/`, `backend/alembic/`. Extract explicit rules (logging, DB
   access, typing, design tokens, etc.).

Build a mental (or written) set: **"already codified in {source}"** for each convention
you find. This prevents Phase 3 from producing noise about things that are well-covered.

---

## Phase 2 — Explore (organic + grep signals)

Use the Agent tool with `subagent_type=Explore` to spawn **two agents in parallel** —
one scoped to the backend, one to the frontend. Give each agent the already-codified
set from Phase 1 so they focus on gaps.

Also run these deterministic grep checks (they find the clean cases quickly):

```bash
# Frontend: env access bypassing lib/env.ts
grep -rn "import\.meta\.env\|process\.env" frontend/web/src \
  --include="*.ts" --include="*.tsx" \
  | grep -v "src/lib/env\.ts"

# Frontend: components/routes making direct API calls instead of going through
# query hooks — structural convention violation (not a type issue)
grep -rn "privateApi\.\|publicApi\." frontend/web/src/screens frontend/web/src/routes \
  --include="*.ts" --include="*.tsx" \
  | grep -v "isAxiosError\|HttpStatusCode"

# Backend: logging bypassing get_logger
grep -rn "logging\.getLogger\|print(" backend/src --include="*.py" \
  | grep -v "get_logger\|# noqa\|def get_logger"

# Backend: DB access outside db/ layer (raw session.execute in routes/tasks)
grep -rn "session\.execute\|session\.get\|session\.add" backend/src \
  --include="*.py" \
  | grep -v "backend/src/fitted_backend/db/"
```

### Backend Explore agent instructions

```
You are surveying the backend/ directory for de-facto conventions — patterns the
Python code consistently follows that aren't yet written down anywhere.

Scope: backend/src/ only. Do not read frontend/ files.

Focus only on GAPS — recurring patterns NOT already in the provided inventory.
Do not surface conventions that are already documented.

For each convention candidate you find:
1. State the convention in one sentence
2. Point to 2–3 files that follow it (evidence)
3. Note any files that deviate (violations)
4. Explain why it looks intentional (not accidental) — e.g. it appears consistently
   across all modules, or there's an obvious "correct" pattern the code converges on

Be conservative: only propose a convention if you see it followed in at least 3 places
and the divergences look like exceptions, not alternatives. When in doubt, mark it
INVESTIGATE rather than proposing codification.
```

### Frontend Explore agent instructions

```
You are surveying the frontend/web/ directory for de-facto conventions — patterns the
TypeScript/React code consistently follows that aren't yet written down anywhere.

Scope: frontend/web/src/ only. Do not read backend/ files.

Focus only on GAPS — recurring patterns NOT already in the provided inventory.
Do not surface conventions that are already documented.

For each convention candidate you find:
1. State the convention in one sentence
2. Point to 2–3 files that follow it (evidence)
3. Note any files that deviate (violations)
4. Explain why it looks intentional (not accidental) — e.g. it appears consistently
   across all modules, or there's an obvious "correct" pattern the code converges on

Be conservative: only propose a convention if you see it followed in at least 3 places
and the divergences look like exceptions, not alternatives. When in doubt, mark it
INVESTIGATE rather than proposing codification.
```

---

## Phase 3 — Present candidates

After the Explore agents return and you've reviewed the grep outputs, assemble a
**ranked candidate list**. Order: undocumented conventions first (real gaps), then
partially-documented ones, then violations of already-documented conventions.

For each candidate, present:

| Field | Content |
|---|---|
| **Convention** | One-sentence statement |
| **Evidence** | 2–3 file paths where it's followed |
| **Violations** | Files that deviate (if any), with approximate count |
| **Status** | `✅ Documented in ADR-NNN` / `⚠️ Partially documented in {file}` / `❌ Undocumented` |
| **Proposed home** | New ADR (cross-cutting decision) and/or specific `CLAUDE.md` section (area rule) — always a `docs/conventions.md` row too |
| **Follow-up** | If violations exist: `Issue` (isolated/small) or `PDR` (touches ≥2 modules) |

Then ask the user: **"Which of these would you like to codify?"** — accept a list of
numbers. Do not scaffold anything yet.

---

## Phase 4 — Scaffold accepted items

For each selected convention, scaffold in this order:

### 4a. New ADR (cross-cutting decisions)

If the proposed home is a new ADR, delegate to the `product-manager` agent — do not
call `new-adr` directly (per root `CLAUDE.md`). Provide the agent with the convention
statement, evidence, and proposed decision so it can scaffold the right artifact:

```
Agent(product-manager): "Create an ADR for the following convention: <statement>.
Context: <evidence from exploration>. Proposed decision: <one sentence>."
```

Then populate the ADR's Context, Decision, and Consequences sections with what you
learned in the exploration. Mark status `Proposed` — the user reviews and accepts.

### 4b. CLAUDE.md addition (area-specific rules)

If the proposed home is a `CLAUDE.md` file, propose the exact text to add — a new
bullet or sub-section — and ask the user to confirm before editing. Keep it concise:
one sentence stating the rule, one example if non-obvious.

### 4c. docs/conventions.md row (always)

Add or refresh the row in `docs/conventions.md` for the accepted convention. The row
must link to the canonical source (the ADR you just created, or the CLAUDE.md section)
— never duplicate the rationale inline. Format:

```markdown
| Convention statement | [Source](relative/path/to/source.md) |
```

If the convention is genuinely cross-cutting (appears in multiple areas), add it to
the Cross-cutting section; otherwise to Backend or Frontend.

### 4d. Follow-up issue or PDR (if violations exist)

For each convention with active violations, scaffold the appropriate artifact:

- **Issue** (isolated fix, single module): create `docs/process/issues/NNN-<slug>.md`
  following the existing issue format (see `074-accessibility-skill.md` for the template).

- **PDR** (refactor touching ≥2 modules): invoke the `new-pdr` skill.

In the issue/PDR body, include the violation list from Phase 3 so the implementer
knows exactly what to fix.

---

## Guardrails

- **Never edit application code.** This skill produces docs and issue/PDR stubs only.
  Code changes go in the follow-up issues/PDRs.

- **Never auto-commit.** After scaffolding, remind the user to review the new files
  and commit via a feature branch + PR (per the `main`-branch rule in root `CLAUDE.md`).

- **Don't re-propose what's already in `docs/conventions.md`.** If a convention
  appears in Phase 1's inventory and has no active violations, skip it entirely.

- **Boundary with `/type-health`:** this skill does not check type tightness — no
  `any` elimination, no generic tightening, no Pydantic/Zod IO boundary checks, no
  escape-hatch or type-checker-config auditing. The structural grep above (direct API
  calls in components) is a *structural/architectural* concern — components should
  fetch via query hooks, not call `privateApi` directly. The *typing* of those calls
  (replacing untyped `privateApi.post` with a typed wrapper function) belongs to
  `/type-health`. If you encounter a pure type-tightness issue, note it as "run
  `/type-health`" and move on — that skill is built and covers heuristics H1–H11
  (see `.claude/skills/type-health/references/type-philosophy.md`).

---

## Closing summary

After scaffolding, print a table:

| Convention | Status | Action taken |
|---|---|---|
| … | Undocumented / Partially / Documented | ADR drafted / CLAUDE.md updated / conventions.md row added / Issue #NNN created / Skipped |

Close with: *"No application code was modified. Review the scaffolded docs and issue
stubs, then open a PR via a feature branch."*
