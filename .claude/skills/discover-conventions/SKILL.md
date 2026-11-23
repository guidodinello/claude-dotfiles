---
name: discover-conventions
description: 'Find implicit codebase conventions and propose codifying them as ADR drafts, CLAUDE.md rules and index rows.'
---

# Discover Conventions

Surface the implicit conventions this codebase follows but hasn't yet codified, then
help turn them into ADRs, `CLAUDE.md` rules, and `docs/conventions.md` index entries.

A healthy, well-documented codebase should produce **few new findings** — most
conventions are already documented. The expected output of a run is a short list of
genuine gaps, not an exhaustive catalogue of what already exists.

---

## Phase 0 — Discover source roots

Do not assume a layout. Before running any command below, find the roots and
use them in place of the `<placeholders>`:

- `<frontend-project>`: a directory with a `package.json` (`git ls-files '*package.json'`, ignoring `node_modules`) whose `src/` holds the UI code. `<frontend-src>` is that `src/`.
- `<backend-project>`: a directory with a `pyproject.toml` (`git ls-files '*pyproject.toml'`). `<backend-src>` is its source root (`src/` or the package directory) and `<backend-pkg>` the importable package under it.

If a root this skill needs cannot be found, stop and ask the user. An empty grep
result is never a clean audit: confirm each root exists and holds files before
reporting zero findings.

The grep checks in Phase 2 (`lib/env.ts`, `get_logger`, `privateApi`/`publicApi`, `db/` layer) are examples of conventions one project had; swap in this project's equivalents, or drop the check if the project has no such convention.

---

## Phase 1 — Know what's already documented

Before exploring, build an inventory of what's already codified so you don't
re-propose it.

**Read these sources in order:**

1. `docs/conventions.md` — the central index (if it exists). This is your starting set.
2. All ADRs in `docs/process/adr/` — scan titles first via the `README.md`, then read
   any whose title suggests a convention rather than a one-time decision.
3. Every `CLAUDE.md` in the repo (`git ls-files '*CLAUDE.md'`). Extract explicit rules
   (logging, DB access, typing, design tokens, etc.).

Build a mental (or written) set: **"already codified in {source}"** for each convention
you find. This prevents Phase 3 from producing noise about things that are well-covered.

---

## Phase 2 — Explore (organic + grep signals)

Use the Agent tool with `subagent_type=Explore` to spawn **two agents in parallel** —
one scoped to the backend, one to the frontend. Give each agent the already-codified
set from Phase 1 so they focus on gaps.

Also run these deterministic grep checks (they find the clean cases quickly).
Then, if `docs/conventions-scans.md` exists, run the project-specific scans it
lists and honour the known exceptions it records — do not re-file a documented
exception as a finding.

```bash
# Frontend: env access bypassing lib/env.ts
grep -rn "import\.meta\.env\|process\.env" <frontend-src> \
  --include="*.ts" --include="*.tsx" \
  | grep -v "src/lib/env\.ts"

# Frontend: code making direct API calls instead of going through the project's
# typed wrappers / query hooks — structural convention violation (not a type
# issue). Scope is all of src/, not just screens/ + routes/: violations tend to
# hide in lib/ and store/. -U is required because a call chain often breaks
# across lines (`void api\n  .get(...)`). Uses rg, not grep — GNU grep has no
# --multiline. Replace `privateApi|publicApi` with your HTTP client's names.
rg -nU --multiline '(privateApi|publicApi)\s*\.' <frontend-src> -g '*.ts' -g '*.tsx' \
  | grep -v "src/lib/api\.ts\|__tests__\|isAxiosError\|HttpStatusCode"

# Frontend: design-token bypasses, part 1 — framework utility literals (e.g.
# Tailwind palette classes) that the project's token rules forbid. Any hit is a
# violation, not a candidate. Adjust the pattern to the project's banned set.
grep -rnE "text-red-|border-red-|bg-red-|text-green-|bg-green-|bg-black/|text-gray-|bg-gray-" \
  <frontend-src>/screens <frontend-src>/components \
  --include="*.tsx" --include="*.ts"

# Frontend: design-token bypasses, part 2 — raw colour literals in inline
# `style={{…}}` props. The utility-class pattern above structurally CANNOT see
# these. Scope is all of src/, since an inline style can appear anywhere.
#
# 6- and 8-digit hex. Deliberately NOT {3,8}: a 3-digit run matches issue and PR
# references like `PR #613` in prose, which is the whole false-positive class.
grep -rnE "#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?\b" <frontend-src> \
  --include="*.ts" --include="*.tsx"

# 3-digit hex, but only when it contains a letter — `#fff`/`#a1b` are colours,
# `#613` is a PR number. Catches the short form without the prose noise.
grep -rnE "#[0-9a-fA-F]{2}[a-fA-F]\b|#[a-fA-F][0-9a-fA-F]{2}\b" <frontend-src> \
  --include="*.ts" --include="*.tsx"

# Colour functions. No false-positive class — there is no other reason for
# `rgba(` to appear in a .ts/.tsx file.
grep -rnE "\b(rgba?|hsla?)\(" <frontend-src> --include="*.ts" --include="*.tsx"

# Every colour hit is a violation unless the token source (theme CSS / tokens
# file) genuinely has no token for it. Check the numbers against it before
# believing otherwise — hits are often a token respelled numerically.

# Backend: logging bypassing get_logger
grep -rn "logging\.getLogger\|print(" <backend-src> --include="*.py" \
  | grep -v "get_logger\|# noqa\|def get_logger"

# Backend: DB access outside db/ layer (raw session.execute in routes/tasks)
grep -rn "session\.execute\|session\.get\|session\.add" <backend-src> \
  --include="*.py" \
  | grep -v "<backend-pkg>/db/"
```

### Backend Explore agent instructions

```
You are surveying the `<backend-project>` directory for de-facto conventions — patterns the
Python code consistently follows that aren't yet written down anywhere.

Scope: <backend-src>/ only. Do not read frontend files.

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
You are surveying the `<frontend-project>` directory for de-facto conventions — patterns the
TypeScript/React code consistently follows that aren't yet written down anywhere.

Scope: <frontend-src>/ only. Do not read backend files.

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

If the proposed home is a new ADR, use the project's ADR agent or skill if it
defines one (check the project's `CLAUDE.md` and `.claude/agents/`, `.claude/skills/`).
Otherwise draft the ADR inline in the project's ADR folder and show it to the user.
Give an ADR agent the convention statement, evidence, and proposed decision so it
can scaffold the right artifact:

```
Agent(<project ADR agent>): "Create an ADR for the following convention: <statement>.
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
  following the existing issue format (copy the format of an existing issue file in that folder).

- **PDR** (refactor touching ≥2 modules): use the project's PDR skill if it
  defines one; otherwise draft the PDR inline and show it.

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
