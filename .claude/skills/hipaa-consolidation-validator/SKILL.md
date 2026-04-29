---
name: audit-consolidation-validator
description: >
  Validate and repair a client-facing consolidated audit document against a set of internal
  audit files. Use this skill whenever the user asks to validate, check, review, consolidate, or
  prepare any audit for client delivery — especially when internal audit versions exist alongside
  a consolidated doc. Works for any audit type: HIPAA, security, permissions, database, or other.
  Trigger when the user says things like "is the consolidated version accurate?",
  "validate the audit before sending to the client", "does the summary match the findings?",
  "process the audit docs", or "consolidate these audit files". Also trigger when the user shows
  you an audit Overall Assessment paragraph and asks if it looks right.
---

## What this skill does

You are validating a client-facing consolidated audit document against one or more internal
audit files. The goal is to catch the class of errors that arise when a consolidated doc falls
out of sync with internal audit iterations: stale severity counts in the Overview, false positives
that slipped through, missing findings from newer audits, and broken finding-ID cross-references.

For HIGH and CRITICAL findings, you also verify each one against the actual codebase using a
sub-agent, because a finding that references a non-existent route or function is a credibility
problem when delivered to a client.

---

## Step 0: Locate files

If the user did not specify paths, look for audit files under `**/docs/audits/`. Common patterns:
- Internal audit files: date-stamped or iteration-named `.md` files (e.g. `*_AUDIT_2026-*.md`, `*-v2.md`)
- Consolidated doc: files with names like `*consolidated*`, `*Compliance*`, `*-final*`

If the audit type is known (hipaa, security, permissions, database), narrow the search to the
relevant subdirectory. Confirm paths with the user before proceeding if ambiguous.

---

## Phase 1: Parse the internal audits

Read every internal audit file. For each one, extract and record:

- **Date** and **commit hash** from the header
- **All findings**: severity (HIGH/MEDIUM/LOW/INFO), ID (e.g. M-1, H-1), title, and status
  - Status values: open, closed, partial, false-positive
  - A finding is a false positive when any internal audit file contains explicit language like
    "is a false positive", "false positive", or "no action required" for that finding
- **Positive controls** (I-* items): ID and title
- **Explicit false-positive declarations**: capture the exact finding ID and the reason given

Process audits in chronological order (oldest first). When the same finding ID appears across
multiple audits, the most recent status wins.

---

## Phase 2: Parse the consolidated doc

Read the consolidated document and extract:

- **Severity counts stated in the Overall Assessment paragraph**: look for phrases like
  "six medium-severity gaps", "one high-severity finding", "two low findings", etc.
- **All findings present**: severity section heading, finding ID, and title
- **Finding IDs referenced in the Prioritized Remediation tables**: every ID that appears
  in the table rows (e.g. "M-1", "H-1", "L-2")
- **Any internal-version language**: phrases like "prior audit", "internal version", "prior
  finding", references to specific internal file names, or auditor tool names (e.g. "Claude Code",
  "claude-sonnet")

---

## Phase 3: Cross-reference and build the issue list

Compare Phase 1 and Phase 2 results. Build a structured list of issues in these categories:

1. **Missing findings**: an open finding in the internal audits is absent from the consolidated doc
2. **False positives included**: a finding explicitly marked as a false positive in any internal
   audit is still present in the consolidated doc
3. **Overall Assessment mismatch**: the severity counts stated in the Overall Assessment paragraph
   do not match the actual finding counts in the consolidated doc's findings sections
4. **Stale ID references**: a finding ID appears in a Remediation table but has no corresponding
   finding section in the document (e.g. table says "L-1" but the findings section starts at "L-2")
5. **ID gaps**: finding numbering within a severity tier is non-contiguous (e.g. M-1 through M-10,
   then M-12 with no M-11)
6. **Internal version leakage**: language in the consolidated doc that references internal audit
   mechanics and would look odd to a client

For each issue, record: type, finding ID (if applicable), and a one-line description.

---

## Phase 4: Code verification for HIGH and CRITICAL findings

For every HIGH or CRITICAL severity finding in the consolidated doc, spawn a sub-agent
(subagent_type: Explore) in parallel. Give each sub-agent:

- The finding ID, title, and full text of the finding (including the specific file:line references)
- This question: "Does this finding accurately describe the current codebase? Check whether the
  route, function, pattern, or code reference described actually exists at the path and line cited.
  Report one of: confirmed / false-positive / partially-accurate. Include one sentence of evidence."

Wait for all sub-agents to return, then record their verdicts in a Code Verification table.

If a HIGH/CRITICAL finding comes back as false-positive from the sub-agent, add it to the issue
list under category 2 (False positives included) with the sub-agent's evidence.

---

## Phase 5: Auto-fix mechanical issues, flag the rest

After building the complete issue list, apply fixes in this order:

### Auto-fix (do these silently, then report what was done):
- **Stale ID references in Remediation tables**: update each table row to use the current correct
  finding ID (e.g. replace "L-1" with "M-11" if that is the renumbered finding)
- **Overall Assessment severity counts**: recount the actual findings by severity and rewrite
  only the count phrases in the Overall Assessment paragraph (e.g. "six medium-severity gaps"
  becomes "eleven medium-severity gaps"). Do not rewrite the substance of the paragraph.

### Flag for human review (report but do not change):
- Missing findings
- False positive inclusions (including any caught by sub-agents in Phase 4)
- Severity escalations: findings that appear at a different severity in the consolidated vs. the
  internal audits
- New findings in the consolidated that do not appear in any internal audit (these may be
  intentional additions, but the human should confirm)
- Internal version leakage (suggest the replacement text but do not apply it)

---

## Output format

Present the report in this order. Use no em dashes — use colons, commas, or parentheses instead.

```
## Consolidation Validation Report

### Code Verification (HIGH/CRITICAL findings)
| Finding | Verdict | Evidence |
|---------|---------|----------|
| H-1: ... | confirmed | ... |

### Issues Found
| # | Type | Detail | Auto-fixed? |
|---|------|--------|-------------|
| 1 | Overall Assessment mismatch | States "six medium" but document has 11 medium findings | Yes |
| 2 | False positive included | M-11 was called a false positive in the internal audit (route does not exist) | No — remove manually |
| 3 | Stale ID reference | Remediation table row "L-1" has no matching finding; should be M-11 | Yes |

### Summary
X issues found. Y auto-fixed. Z require human review.
```

After the report, apply the auto-fixes to the consolidated file directly. Then list each
auto-fixed change in a "Changes Applied" section at the end so the user can verify.

---

## Writing style rules (for any text you write or rewrite)

- No em dashes. Use colons, commas, or parentheses.
- Do not reference internal audit file names in the consolidated doc.
- Do not reference the auditor tool name in the consolidated doc.
- Finding IDs in the consolidated doc should be self-contained (a reader should not need the
  internal files to understand them).
