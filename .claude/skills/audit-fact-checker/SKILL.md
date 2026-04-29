---
name: audit-fact-checker
description: >
  Verify reported audit findings against the actual codebase to confirm whether each is a real
  bug or a false positive. Use this skill whenever the user wants to spot-check an audit report,
  validate specific findings before client delivery, or triage which issues are worth spending
  engineering time on. Works for any audit type: HIPAA, security, permissions, database, or other.
  Trigger when the user says things like "is this finding real?", "fact-check the audit",
  "verify these bugs against the code", "which of these are false positives?", or "validate
  finding H-1". Can check a single finding, a list of IDs, or all findings of a given severity.
---

## What this skill does

You are a fact-checker. Given an audit document and a codebase, you verify each reported finding
against the actual code. For each finding, you spawn a parallel sub-agent that searches the
codebase and returns a verdict: **confirmed**, **false-positive**, or **partially-accurate**.

You do not re-audit the codebase or look for new issues. You only verify what the audit claims.

---

## Step 0: Gather inputs

Collect from the user or infer from context:

1. **Audit file path** — required. If not provided, look for audit files under `**/docs/audits/`.
   Common patterns: `*consolidated*`, `*Compliance*`, `*-final*`, date-stamped `.md` files.
   Ask the user if ambiguous.

2. **Scope** — which findings to verify. Defaults and priority:
   - If the user named specific finding IDs (e.g. `H-1,M-3`): verify only those.
   - If the user said `--severity all` or "check everything": verify all severities.
   - If the user named a severity (e.g. "check all highs"): verify that severity only.
   - Default (no qualifier): verify CRITICAL and HIGH only.

3. **Codebase root** — where to search. If the user is in a project directory, use that.
   If the audit file references a system name or repo name, look for it as a sibling directory.
   Ask the user if you cannot determine where the codebase lives.

---

## Step 1: Parse findings from the audit doc

Read the audit document. Extract every finding that falls within the declared scope.

For each finding, capture:
- **ID**: e.g. `H-1`, `M-4`, `C-2`
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW / INFO
- **Title**: the short descriptor on the finding heading
- **Full body**: the complete finding text — file paths, line numbers, code snippets, risk
  description, and recommendation. Keep this verbatim; the sub-agent needs everything.
- **File references**: any `path/to/file.ts:line` patterns cited in the finding body

If the audit has no file:line references for a finding (i.e. it describes a behavioral gap
rather than a specific code location), note this — the sub-agent will need to search more broadly.

---

## Step 2: Spawn one sub-agent per finding, all in parallel

For each finding in scope, spawn a sub-agent with `subagent_type: Explore`.

The sub-agent prompt must include all of the following:

```
You are fact-checking a single reported audit finding against the codebase at <codebase_root>.
Your job is to determine if the finding accurately describes reality. Do not fix anything.

FINDING ID: <id>
SEVERITY: <severity>
TITLE: <title>

FULL FINDING TEXT:
<verbatim finding body>

FILE REFERENCES CITED:
<list of file:line references, or "none stated">

VERIFICATION STEPS — work through these in order, stopping when you have enough evidence:

1. For each cited file:line reference:
   - Does the file exist at that path?
   - Does the code at (or near) that line match what the finding describes?
   - If the file or line doesn't exist, that is evidence of a false positive.

2. For the core claim (what the finding says is wrong):
   - If the finding says something is MISSING (e.g. "no MFA enforcement"):
     grep the codebase for any code that would constitute the control being present.
     Search broadly — look for the function name, the middleware name, the check pattern.
     If you find it: report where and what you found.
     If you don't: that confirms the gap.
   - If the finding says something IS PRESENT and problematic (e.g. "raw IP written to logs"):
     grep for the pattern. Confirm it exists and is reachable.
   - If the finding describes a behavioral flow (A calls B which leaks C):
     trace the call chain and confirm each step.

3. Check if there is any remediation code that postdates the finding:
   - Look for recent changes near the cited files (git is not available — infer from code patterns).
   - If a fix is clearly in place (the vulnerable code no longer exists, or a guard was added),
     report it as potentially remediated.

VERDICT — choose exactly one:
- **confirmed**: the finding accurately describes a real gap in the current code
- **false-positive**: the finding is wrong — the problem does not exist, the code reference
  is invalid, or a fix is already in place
- **partially-accurate**: the core issue exists but details are wrong (wrong line, wrong severity,
  partially fixed, or only present in some code paths)

RESPONSE FORMAT — return exactly:
VERDICT: <confirmed|false-positive|partially-accurate>
EVIDENCE: <one or two sentences — cite the specific file:line or pattern you found or did not find>
NOTES: <optional — any nuance, e.g. "fix appears to be in place but only for the happy path">
```

Dispatch all sub-agents simultaneously. Do not wait for one before starting the next.

---

## Step 3: Collect results and build the report

Wait for all sub-agents to return. For each finding, record:
- Finding ID and title
- Verdict
- Evidence sentence(s)
- Notes (if any)

Then produce the report.

---

## Output format

```
## Audit Fact-Check Report

**Audit:** <file name>
**Scope:** <e.g. "CRITICAL and HIGH (default)" or "All severities" or "H-1, M-3, M-7">
**Findings checked:** <N>
**Codebase:** <path used>

### Verdict Summary
| Finding | Severity | Verdict | Evidence |
|---------|----------|---------|----------|
| H-1: MFA flag exists but is never enforced | HIGH | confirmed | No MFA enforcement found in middleware or route handlers; requireMfa field exists in settings schema but is never read at auth time |
| M-3: Raw IP in audit_logs | MEDIUM | confirmed | audit_logs insert at src/lib/audit.ts:47 writes req.ip directly with no hashing |
| M-7: Cross-tenant template exposure | MEDIUM | partially-accurate | Templates are returned without org scoping at routes/templates.ts:112, but only for admin role — regular users are gated |

### False Positives
List each false-positive finding here with the sub-agent's evidence. These should be
reviewed before the next audit delivery.

| Finding | Reason |
|---------|--------|
| L-2: ... | File src/foo.ts does not exist; route was removed in a prior refactor |

### Confirmed Findings
List confirmed findings grouped by severity, highest first. For each one include the
evidence sentence so engineers know exactly where to look.

### Needs Human Review
List partially-accurate findings with the nuance noted. These require a judgment call on
whether the finding should be kept as-is, downgraded, or split.

### Summary
- Confirmed: X of N
- False positives: Y of N
- Partially accurate: Z of N
```

After the report, if any false positives were found, note that the `audit-consolidation-validator`
skill can be used to remove them from the consolidated doc and recount the severity totals.

---

## Confidence guidance for sub-agents

Behavioral findings ("X is never done anywhere") are harder to confirm than reference findings
("X exists at file:line"). For behavioral findings, a thorough grep that finds nothing is strong
evidence of confirmation, but a brief search is not. The sub-agent should state explicitly how
broadly it searched (e.g. "searched all .ts files for `requireMfa` — not found").

For reference findings where the file:line exists but the code has shifted slightly (e.g. the
pattern is at line 52 instead of line 47), treat this as **confirmed** with a note, not
false-positive — line drift is expected between audit and review.
