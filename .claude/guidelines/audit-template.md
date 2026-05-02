# Audit Report Template

Shared structure for all audit skills (hipaa-audit, security-audit, db-scalability-audit, permissions-audit). Each skill adds its own discovery steps, surface map, and domain-specific violation patterns on top of this shared reporting contract.

---

## Document Header

```markdown
# <Audit Type> Audit

**System:** <app name>
**Date:** <YYYY-MM-DD>
**Auditor:** Claude Code (<model id>)
**Scope:** <what was covered>
```

---

## Overall Assessment

2–4 sentence executive summary: what the system handles well, where the highest-risk gaps concentrate, and the single most important action. This is what a non-technical stakeholder reads first.

---

## Surface Map

Audit-specific. Each skill defines its own "before findings" tables here:
- hipaa-audit: PHI-Bearing Tables + External Services Receiving PHI
- security-audit: Entry Points + User Input → Dangerous Sinks
- db-scalability-audit: Provider + Schema + Growth trajectory
- permissions-audit: Roles/Permissions Matrix

---

## Findings

Group findings under severity headings. Use sequential IDs within each severity so the remediation table can reference them unambiguously.

```markdown
### CRITICAL
**C-1: <short title>**
- Location: `path/to/file.ts:line`
- Finding: What you observed
- Risk: The specific harm this enables (cite CFR section, CVE, or standard where relevant)
- Recommendation: Concrete fix

### HIGH
**H-1: <short title>**
...

### MEDIUM
**M-1: <short title>**
...

### LOW
**L-1: <short title>**
...

### INFO
**I-1: <short title>**
...
```

### Severity Levels

| Level | Meaning |
|---|---|
| **CRITICAL** | Directly exploitable or actively exposing data today. Dead code cannot be CRITICAL — if the path has no production callers (verify via grep excluding tests), cap at MEDIUM. |
| **HIGH** | Serious risk but requires specific conditions (auth required, chaining with another issue, specific environment). |
| **MEDIUM** | Vulnerability or gap exists with meaningful mitigating factors. Latent risk in dead code belongs here. |
| **LOW** | Defense-in-depth gaps; no direct exploit path today. |
| **INFO** | Two uses: (1) observations that cannot be verified from static analysis alone (server config, third-party SLAs, BAA status); (2) **positive controls** — things the codebase does correctly. Prefix positive controls with "Positive control —". |

Do not put "What's Working Well" in a separate section. Positive controls belong in `### INFO` as `I-*` findings — this keeps all observations in one place.

### Dead Code Rule

Before assigning CRITICAL or HIGH to any finding, verify the vulnerable function/handler is called in production code. Grep for it, explicitly excluding test files (`**/__tests__/**`, `**/*.test.ts`, `**/*.spec.ts`):
- Callers only in tests → downgrade to MEDIUM, note "no production callers — latent risk only"
- No callers at all → same treatment, recommend deletion over patching
- Production callers confirmed → proceed with original severity

---

## Prioritized Remediation

Split into time-based tiers. Include an **Effort** column. Reference finding IDs, not titles.

### Effort Labels

| Label | Meaning |
|---|---|
| Tiny | < 30 min — a one-liner, a config flag, a header |
| Small | 30 min – 2 hr — a single function, a middleware addition |
| Medium | 2–8 hr — a validation layer, a schema change, cross-service fix |
| Large | 1–3 days — architectural change |
| XL | > 3 days — multi-sprint, staged rollout |

```markdown
## Prioritized Remediation

### Address immediately
| # | Finding | Effort |
|---|---|---|

### Address within 30 days
| # | Finding | Effort |
|---|---|---|

### Address within 90 days
| # | Finding | Effort |
|---|---|---|
```

---

## Sources Cited

End with a **Sources** section listing every external URL referenced in the report — OWASP articles, CVE advisories, framework docs, provider limits. No citation, no external claim.

```markdown
## Sources

- [Source title](url) — one-line description of what it supports
```

---

## Key Files Reference

End with a two-column table mapping file paths to their audit-relevant purpose. Helps engineers navigate to the right place when acting on findings.

```markdown
## Key Files Reference

| File | Purpose |
|---|---|
| `path/to/file.ts` | Description |
```
