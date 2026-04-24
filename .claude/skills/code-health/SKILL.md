---
name: code-health
description: >
  Perform a codebase readiness and technical debt analysis covering scale metrics, type safety,
  dead code, test coverage, complexity hotspots, and dependency vulnerabilities. Use this skill
  whenever the user asks for a code health check, codebase readiness assessment, technical debt
  review, pre-launch audit, or wants to understand the overall quality and risk profile of a
  codebase. Also trigger when the user asks about dead code, test coverage gaps, complexity
  hotspots, or dependency vulnerabilities as part of a broader audit. Produces 6 structured
  section files plus a consolidated report ready to include in a client deliverable.
---

## Overview

This skill produces a **Codebase Readiness & Technical Debt** report across 6 sections:

1. **Codebase scale** — LOC by language, backend/frontend/test split (cloc)
2. **Type safety** — error count, categories, critical path impact (tsc)
3. **Dead code** — unused files, exports, deps with focus on security-critical paths (knip)
4. **Test coverage** — coverage matrix against critical areas, dangerous untested paths
5. **Complexity hotspots** — top 5 risky functions ranked by risk not size
6. **Dependency vulnerabilities** — snyk, npm audit, semgrep; real findings vs false positives

All sections run as parallel subagents to keep the main context clean. The main session only writes the final consolidated report.

---

## Step 0: Setup

**Resolve output directory:**
- Prefer `my-dev-things/docs/tools-output/` if it exists
- Otherwise use `docs/audit/` or create `.audit-output/` at repo root

**Capture scan metadata** (pass to all subagents):
```bash
git rev-parse --short HEAD   # commit hash
date +%Y-%m-%d               # scan date
```

---

## Step 1: Spawn all subagents in parallel

Launch all 6 in a single message so they run concurrently. All agents should save their output file to the resolved output directory before finishing.

---

### Agent 1 — Codebase scale (cloc)

**Type:** general-purpose (needs Bash)

```
Run cloc to collect codebase scale metrics. Save results to [OUTPUT_DIR]/cloc.md.

Commands to run from the repo root:
  cloc . --exclude-dir=node_modules,.git,dist,.wrangler --include-lang=TypeScript,JavaScript,SQL,CSS,HTML
  cloc backend/src --include-lang=TypeScript,SQL
  cloc frontend/src --include-lang=TypeScript,CSS,HTML
  find . -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" | grep -v node_modules | wc -l

If cloc is not installed, use: npx cloc [same args]

Write cloc.md with:
- Total LOC table by language (code only, not blanks/comments)
- Backend vs frontend vs shared split
- Test file count and ratio vs production code
- 2-3 sentence narrative for an audit reader

Scan date: [DATE] | Commit: [HASH]
```

---

### Agent 2 — Type safety (tsc)

**Type:** general-purpose (needs Bash)

```
Run TypeScript type checking and save results to [OUTPUT_DIR]/tsc.md.

Commands:
  npx tsc --noEmit 2>&1

If the project has workspace packages (backend/, frontend/), run per workspace too.
Count errors: npx tsc --noEmit 2>&1 | grep "^error TS" | wc -l

Write tsc.md with:
- Total error count
- Breakdown: logic/type errors vs configuration errors (missing @types packages)
- Whether errors appear in critical paths (auth, PHI handling, payments, webhooks)
- 2-3 sentence narrative

Zero real logic errors is a strong positive finding — say so explicitly.
Configuration-only errors (missing @types for dev tooling) are not production risks.

Scan date: [DATE] | Commit: [HASH]
```

---

### Agent 3 — Dead code (knip)

**Type:** general-purpose (needs Bash)

```
Run knip to detect dead code and save results to [OUTPUT_DIR]/knip.md.

Command:
  npx knip 2>&1

Write knip.md with:
- Counts: unused files, exports, exported types, devDependencies
- High-priority unused files: flag anything in backend route handlers, auth modules,
  webhook handlers — dead code in deployed security-critical paths matters most
- Unused npm dependencies (reduce attack surface)
- False positive note: monorepo shared types often false-positive due to re-export
  patterns; note this explicitly rather than listing them as real findings
- 2-3 sentence narrative for an audit reader

Scan date: [DATE] | Commit: [HASH]
```

---

### Agent 4 — Dependency vulnerabilities (snyk + npm audit + semgrep)

**Type:** general-purpose (needs Bash)

```
Run dependency and static analysis scans, then write a classified findings report
to [OUTPUT_DIR]/dependency-vulns.md.

Commands:
  npm audit --all-workspaces 2>&1
  snyk test --all-projects 2>&1
  semgrep scan 2>&1

Run all three. If a tool is not installed or not authenticated, note it and skip.
Save raw outputs to [OUTPUT_DIR]/npm.txt, snyk.txt, semgrep.txt respectively.

Then write dependency-vulns.md with findings classified as:
  Real Finding — confirmed by 2+ tools, or clearly exploitable
  Mitigated — vulnerability exists but code review shows it's handled (read the file)
  False Positive — tool rule doesn't apply to the language/context

Common Semgrep false positives to recognize:
- dangerouslySetInnerHTML: check if DOMPurify or equivalent wraps it — if yes, mitigated
- Non-literal RegExp: check if variable is run through an escape function first
- Unsafe format string on JS template literals: C printf rules don't apply to JS
- GitHub Actions shell injection via workflow_dispatch: real but MEDIUM not HIGH
  (requires repo write access to trigger, not externally reachable)

Structure dependency-vulns.md as:
- Real findings table (severity, package/file, description, fix)
- Mitigated section with evidence from code
- False positives section with dismissal reasoning
- Per-workspace scan summary (which are clean, which have vulns)
- 2-3 sentence narrative for an audit reader

Scan date: [DATE] | Commit: [HASH]
```

---

### Agent 5 — Test coverage inventory

**Type:** Explore

```
Do a qualitative test coverage inventory for a codebase readiness audit.
Save your findings to [OUTPUT_DIR]/test-coverage.md.

1. Find all test files (*.test.ts, *.test.tsx, *.spec.ts, __tests__/ directories)
2. Read enough of each to understand what it covers
3. Map coverage against these critical areas:
   - User/patient authentication (session creation, magic link, token expiry, reuse prevention)
   - Staff auth and RBAC enforcement (role boundaries, permission escalation scenarios)
   - CSRF protection
   - Core business object lifecycle (orders, payments, status transitions)
   - Payment/billing webhook signature verification and idempotency
   - Third-party integration webhooks
   - PHI/sensitive data logger redaction (if this is a healthcare app)
   - Protected route auth enforcement on the backend (not just frontend guards)
   - Email/notification injection prevention

Mark each: Covered / Partially Covered / Not Covered

Then identify the 5-8 most dangerous untested paths from a launch-risk perspective.
For each gap: what it is, what failure it enables, which file to add the test to.

If this is a healthcare/HIPAA codebase (look for PHI, patient data, HIPAA references),
weight auth flows, PHI handling, and audit logging gaps as highest priority.

Write test-coverage.md with:
- Coverage matrix table
- Dangerous untested paths with severity (CRITICAL / HIGH / MEDIUM)
- File pointers for where to add missing tests
- 2-3 sentence narrative for a client-facing audit report

Scan date: [DATE] | Commit: [HASH]
```

---

### Agent 6 — Complexity hotspots

**Type:** Explore

```
Identify complexity hotspots for a codebase readiness audit.
Save your findings to [OUTPUT_DIR]/complexity.md.

Focus on functions that combine HIGH COMPLEXITY with HIGH RISK — size alone is not
the criteria. Read the actual files in these areas:
- Auth and session management (login, token creation, session stores)
- Payment and webhook processing
- PHI or sensitive data handling (email sends, data exports, audit logging)
- Scheduled/background jobs
- Core business object update handlers

For each hotspot, look for:
- Long functions (100+ lines) with multiple responsibilities
- Deep nesting (4+ levels of if/for/try)
- Silent error swallowing (catch blocks that ignore or log-and-continue)
- External calls without explicit error propagation
- Race conditions (concurrent state mutations without atomic guarantees)

Pick the top 5 ranked by RISK (not size). For each:
- File:line range and function name
- Specific risk pattern (silent catch, nesting, race condition, etc.)
- Whether it's in a critical path (auth, payment, PHI)
- One concrete recommendation

If this is a healthcare/HIPAA codebase, weight silent failures in PHI-touching
code highest — they create audit trail gaps that are compliance violations.

Write complexity.md with:
- Top 5 hotspots with file:line, risk level, description, recommendation
- A summary of the common pattern if one exists
- 2-3 sentence narrative for a client-facing audit report

Scan date: [DATE] | Commit: [HASH]
```

---

## Step 2: Write the consolidated report

Once all 6 agents complete and all section files exist in the output directory, write `code-health-report.md`:

```markdown
# Codebase Readiness & Technical Debt

**Audit Date:** YYYY-MM-DD | **Commit:** <hash>
**Tools:** cloc, tsc, knip, npm audit, Snyk, Semgrep, manual exploration

---

## 1. Codebase Scale
[Key numbers from cloc.md + narrative]

## 2. Type Safety
[Verdict + any errors that matter from tsc.md]

## 3. Dead Code
[High-priority findings + false positive note from knip.md]

## 4. Test Coverage
[Coverage matrix + top dangerous gaps from test-coverage.md]

## 5. Complexity Hotspots
[Top 5 table + common thread from complexity.md]

## 6. Dependency Vulnerabilities
[Real findings only + false positive count from dependency-vulns.md]

---

## Recommendations Summary

| Priority | Finding | Action |
|---|---|---|
| Before launch | ... | ... |
| Post-launch | ... | ... |
```

Pull the 6-10 most important items from all sections. Tag each "Before launch" or "Post-launch" based on risk. Distinguish signal from noise explicitly — false positives that were dismissed should be noted to build trust in the report.

---

## Notes for healthcare/HIPAA codebases

If the codebase handles patient data, weight these findings highest regardless of which section they come from:
- PHI logger redaction with no test coverage
- Silent error swallowing in email/notification paths (audit trail gaps)
- Magic link token reuse or expiration not enforced
- Protected patient endpoints not verified on the backend
- Dead webhook handlers in the deployed artifact
