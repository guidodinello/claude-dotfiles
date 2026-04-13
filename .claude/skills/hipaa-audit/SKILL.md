---
name: hipaa-audit
description: >
  Perform a HIPAA Security Rule compliance audit on a healthcare codebase. Use this skill whenever the
  user asks for a HIPAA audit, PHI compliance review, security review of a healthcare app, production
  readiness check of a patient-facing system, or wants to find where protected health information is
  exposed or mishandled. Also trigger when the user asks about ePHI risks, BAA coverage, audit trail
  gaps, or access control issues in medical software. Do not wait for the user to say "HIPAA" explicitly
  — trigger whenever the codebase clearly handles patient data and a security or compliance concern is raised.
---

## How to Run This Audit

Treat this as an investigation, not a checklist. Your job is to map how PHI flows through the system and find the gaps between what security controls exist and where they're actually applied.

---

## Step 0: Check for existing audit docs (do this before anything else)

Glob for `**/HIPAA*.md`, `**/hipaa*.md`, `**/compliance*.md`, `**/COMPLIANCE*.md`, `**/security-audit*.md` in the repo root and any `docs/` directories. If prior audit reports exist:

- Read them to understand what has already been found and remediated
- Note which findings are marked REMEDIATED — do not re-raise these unless you find the fix is incomplete or was reverted
- Note any open recommendations listed as "not yet implemented" — these are candidates to carry forward
- Note any BAA statuses already confirmed by the team, so you don't flag them as unverified
- If the prior doc conflicts with what you observe in code (e.g., says a fix was applied but the code doesn't show it), flag the discrepancy explicitly

---

## Step 1: Orient yourself (do this first, before evaluating any control)

Run these 7 discovery steps before forming any conclusions. Together they give you a map of the PHI surface.

**1. Find the data model**
Glob for `schema.sql`, `schema.prisma`, migration files (`**/migrations/**`), ORM model definitions. List every table/entity that contains PHI fields (see PHI field reference below).

**2. Find the auth system**
Grep for session creation (`createSession`, `sign(`, `jwt.sign`, `sessionStorage`, cookie-setting code). Determine: how are sessions created? where are tokens stored? what are the TTLs? is there automatic logoff?

**3. Find the logging system**
Grep for `console.log`, `logger.`, `log.info`, `log.debug`, `log.error`, `winston`, `pino`, `bunyan`. Is there a central logger? Does it have PHI redaction? Find where redaction is defined and verify it's applied everywhere PHI could appear.

**4. Find external integrations**
Grep for `fetch(`, `axios`, `new SomeClient(`, SDK instantiations, and env vars with names like `API_KEY`, `SECRET`, `TOKEN`, `WEBHOOK`. List every third-party service. For each one: does it receive PHI? Is there a BAA?

**5. Find the audit log**
Grep for `auditLog`, `audit_log`, `accessLog`, `logAccess`. Is there one? What does it capture — who, what record, when, from where? Where does it write (same DB as app data is a risk)? What's the retention policy?

**6. Find the patient-facing surface**
Find all routes or endpoints accessible by patients (not just staff). For each one: does it require authentication? Can Patient A access Patient B's records? (IDOR risk — check that queries filter by the authenticated patient's ID, not a user-supplied ID.)

**7. Find the webhook surface**
Grep for route handlers that process inbound webhooks (`/webhook`, `/callback`, `/notify`). For each: is the payload signature verified before processing? What happens to the data after parsing?

---

## PHI Field Reference

PHI is any information that identifies a patient AND relates to their health condition, care, or payment. Combination matters: a weight measurement alone is not PHI; linked to a patient record it is.

**Always PHI when linked to a patient:**
name, dob, date_of_birth, email, phone, address, ssn, zip_code (5-digit), account_number, mrn, patient_id, device_id, ip_address, biometric, photo, insurance_id

**PHI when tied to an individual (not standalone):**
diagnosis, condition, medication, weight, height, bmi, lab_result, prescription, treatment, appointment_date, discharge_date, admission_date

**Grep targets to find PHI handling:**
```
patient_id, patientId, userId (in patient context), email, phone, dob, ssn,
firstName, lastName, first_name, last_name, address, zipCode, diagnosis,
medication, prescription, weight, insurance
```

---

## Investigative Methodology

### Follow the data, not the file structure

Pick a PHI field and trace it forward and backward:
- Where is it written to the DB?
- Where is it read back?
- Where is it logged (directly or via object spread)?
- Where is it sent externally (API calls, emails, webhooks)?

Pick a user action ("staff views patient profile") and trace it end to end:
auth check → DB query → response serialization → client rendering → any side effects (email triggers, audit log writes, analytics events)

Pick an external trigger ("pharmacy webhook arrives") and trace:
authentication check → payload parsing → DB writes → logging → any downstream calls

This surfaces issues that file-by-file review misses — PHI leaking into a log two layers away from where it's read.

### Find the gap between stated intent and actual implementation

When you find a security control (PHI redactor, auth middleware, audit log function):
- Grep for every place it's used
- Grep for every place it *should* be used but isn't
- Never conclude "PHI redaction is implemented" from seeing a redaction utility — verify coverage on every log call that could emit PHI
- Inconsistency is a finding even if the control exists

---

## Violation Patterns

See [`references/violation-patterns.md`](references/violation-patterns.md) for the full catalog of anti-patterns by category:
- Logging violations
- Storage violations
- Transmission violations
- Access control violations
- Audit trail violations
- Secrets and BAA violations

Key patterns to check inline:

**Logging:** Does any logger call receive a patient object, req.body on a PHI endpoint, or an error that wraps a PHI-bearing object? PHI in debug logs is still a violation.

**IDOR:** Find every query that fetches patient data. Does it filter by `WHERE patient_id = $authenticated_patient_id`? Or does it trust a user-supplied ID from the URL/body?

**Session storage:** Grep for `localStorage.set`, `sessionStorage.set`. PHI or session tokens in either is HIGH severity.

**Webhook auth:** Find inbound webhook handlers. Is there a signature verification step before the payload is parsed and trusted?

**Audit trail completeness:** Find every endpoint that reads or writes PHI. Is there an audit log call on each one? Grep for the audit log function and compare usage against PHI endpoints.

---

## Vendor / BAA Checklist

See [`references/vendor-baa.md`](references/vendor-baa.md) for a checklist of common healthcare vendors and what to verify.

When auditing any vendor integration, always answer:
1. Does this vendor receive PHI (even partial — email addresses, order IDs)?
2. Is there a BAA? (You cannot verify this from code — flag as INFO for human review)
3. Is the integration authenticated? For inbound calls: is auth verified before trusting the payload?
4. If this vendor's API key were compromised, what patient data would be exposed?

Common high-risk vendor categories: error monitoring (Sentry, Datadog), analytics (Mixpanel, Segment, Amplitude), email (SendGrid, Mailgun — must have BAA), SMS (Twilio — must have BAA), pharmacy APIs, lab integrations, EHR connectors.

---

## HIPAA Technical Safeguard Reference

The Security Rule (45 CFR § 164.312) has four technical safeguard categories. Distinguish **Required** (must implement) from **Addressable** (implement or document equivalent alternative — addressable does not mean optional).

| Category | Required | Addressable |
|---|---|---|
| Access Control | Unique user IDs, emergency access procedure | Automatic logoff, encryption/decryption |
| Audit Controls | Record/examine ePHI access activity | — |
| Integrity | Authenticate ePHI hasn't been altered | Transmission integrity |
| Transmission Security | — | Encryption in transit (TLS 1.2+ minimum) |

In practice: if the system handles ePHI over the internet with no compensating controls, treat transmission encryption as effectively required. Document any addressable spec you flag.

---

## Reporting Format

### Document header

Start every report with:

```markdown
# HIPAA Security Rule Compliance Audit

**System:** <app name>
**Date:** <YYYY-MM-DD>
**Auditor:** Claude Code (<model id>)
**Scope:** <what was covered — e.g. "Full codebase static analysis — PHI data flows, access controls, audit trails, external integrations, session security, webhook surface, frontend storage">
```

### Overall Assessment

Follow the header with a 2–4 sentence executive summary: what the system does well, where the gaps concentrate, and the highest-severity finding in plain language. This is what a non-technical stakeholder reads.

### PHI Surface Map

Before any findings, include:
1. A **PHI-Bearing Tables** table: table name, PHI fields, encrypted (YES/NO + algorithm)
2. An **External Services Receiving PHI** table: service, PHI received, BAA status (✅ Signed / ⚠️ Verify / ❌ None)

### Findings

Group findings under severity headings. Use sequential IDs within each severity so the remediation table can reference them unambiguously.

```markdown
### CRITICAL
**C-1: <short title>**
- File: `path/to/file.ts:line`
- Finding: What you observed
- Risk: The specific HIPAA violation or patient harm this enables (cite CFR section where relevant, e.g. § 164.312(b))
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

**Severity levels:**
- **CRITICAL** — PHI exposed without authentication, active data breach risk, IDOR between patients
- **HIGH** — PHI in logs, missing audit trail on PHI access, session tokens in localStorage, webhook auth bypassable
- **MEDIUM** — Session TTL too long, missing CSRF on PHI mutations, PHI in URL params, password policy gaps
- **LOW** — Missing security headers, no rate limiting on auth endpoints, non-critical audit gaps
- **INFO** — Two uses: (1) observations/questions that cannot be verified from code (BAA status, server config, key management); (2) **positive controls** — things the codebase does correctly that are worth documenting. Prefix positive controls with "Positive control —" so they're easy to distinguish.

Do not put "What's Working Well" in a separate section. Positive controls belong in `### INFO` as `I-*` findings — this keeps all observations in one place and makes strengths feel as deliberate as gaps.

### Prioritized Remediation

Split into time-based tiers. Include an **Effort** column so engineers can plan. Reference finding IDs, not titles.

```markdown
## Prioritized Remediation

### Address soon
| # | Finding | Effort |
|---|---|---|
| H-1 | <title> | ~2 hr |

### Address within 30 days
| # | Finding | Effort |
|---|---|---|
| M-1 | <title> | ~3 hr |

### Address within 90 days
| # | Finding | Effort |
|---|---|---|
| L-1 | <title> | ~1 hr |
| I-1 | <title> | ~4 hr |
```

### Key Files Reference

End with a two-column table mapping file paths to their HIPAA-relevant purpose. This helps engineers navigate to the right place when acting on findings.
