---
name: meta-skill-hipaa-audit-improver
description: >
  Improve and update the HIPAA audit skill by fetching authoritative regulatory sources, NIST
  guidance, OWASP cheat sheets, and HHS enforcement cases. Use this skill when the user wants
  to refresh or improve the HIPAA audit skill references, keep compliance guidance up to date,
  or strengthen the skill with real enforcement cases and official citations. Trigger phrases:
  "update the HIPAA skill", "refresh the compliance references", "improve the audit skill",
  "run the HIPAA skill updater".
compatibility:
  tools:
    - WebFetch
  allowed_domains:
    - www.ecfr.gov
    - www.hhs.gov
    - csrc.nist.gov
    - pages.nist.gov
    - cheatsheetseries.owasp.org
    - www.hipaajournal.com
---

## What this skill does

Fetches authoritative HIPAA and security sources, compares them against the current skill
reference files, and updates or creates reference files with accurate, cited content.

Only modifies files inside `~/.claude/skills/hipaa-audit/references/`. Never touches `SKILL.md`.

---

## Step 1 — Read current state

Before fetching anything, read every existing reference file:

```
~/.claude/skills/hipaa-audit/SKILL.md
~/.claude/skills/hipaa-audit/references/violation-patterns.md
~/.claude/skills/hipaa-audit/references/vendor-baa.md
~/.claude/skills/hipaa-audit/references/authentication-controls.md        (may not exist yet)
~/.claude/skills/hipaa-audit/references/administrative-safeguards.md      (may not exist yet)
```

Note what each file covers, what looks thin, and what has no authoritative citation.

---

## Step 2 — Fetch authoritative sources

Fetch each URL below. For each one, extract technically actionable content — named controls,
specific requirements, concrete patterns. Skip marketing copy and introductory summaries.

If a fetch fails, note it in the research log (Step 5) and continue — do not halt.

### Regulatory (fetch all)

| URL | What to extract |
|-----|----------------|
| `https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C/section-164.312` | Full text of Technical Safeguards — every standard and implementation spec with Required/Addressable designation |
| `https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C/section-164.308` | Administrative Safeguards — extract only specs with code-auditable implications (access management, incident procedures, contingency plan, evaluation) |
| `https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html` | Security Rule overview — cross-check against existing references for anything missing |
| `https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html` | Minimum necessary standard — extract requirements that translate to API design and data access patterns |

### HHS guidance papers (fetch all)

| URL | What to extract |
|-----|----------------|
| `https://www.hhs.gov/sites/default/files/ocr/privacy/hipaa/administrative/securityrule/techsafeguards.pdf` | Full technical safeguards guidance — extract any implementation detail not already in the references |
| `https://www.hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/index.html` | List of OCR resolution agreements — find the 10 most recent, fetch each, extract: what was violated, what the technical failure was, what remediation was required |

### NIST (fetch all)

| URL | What to extract |
|-----|----------------|
| `https://csrc.nist.gov/publications/detail/sp/800-66/rev-2/final` | Find the PDF or HTML link for NIST SP 800-66r2, fetch it, extract the technical controls checklist |
| `https://pages.nist.gov/800-63-3/sp800-63b.html` | NIST SP 800-63B — extract: password requirements, session management rules, authenticator assurance levels (AAL1/AAL2/AAL3), reauthentication triggers |

### OWASP (fetch all)

| URL | What to extract |
|-----|----------------|
| `https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html` | Session ID properties, cookie attributes, session expiry, concurrent sessions |
| `https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html` | What to log, what NOT to log (sensitive data in logs), log integrity |
| `https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html` | Enforcement patterns, IDOR prevention, least privilege |

---

## Step 3 — Gap analysis

After fetching, compare sources against the current reference files. Build a gap list:

- Requirements in § 164.308 with code-auditable implications not yet covered
- NIST 800-66 controls absent from `violation-patterns.md`
- NIST 800-63B authentication requirements not reflected in `authentication-controls.md`
- OCR enforcement patterns not present in any reference file
- OWASP guidance that would strengthen existing sections

---

## Step 4 — Update reference files

### Always update: `violation-patterns.md`
- Add CFR section citations to any header missing them
- Add or expand sections based on gap analysis
- Add an "OCR Enforcement Cases" section at the bottom — for each case: what was violated,
  what the technical failure was, what remediation was required
- Keep under 600 lines; if it would exceed that, move the enforcement cases to a new file
  `references/ocr-enforcement-cases.md` and link to it

### Always update: `vendor-baa.md`
- Add any vendor categories or specific vendors missing from the current file
- Add notes on which vendors have formal BAA programs with links to their BAA pages where found

### Create if missing: `authentication-controls.md`
Dedicated reference for authentication requirements. Cover:
- § 164.312(d) Person or Entity Authentication requirements
- NIST 800-63B password and session requirements mapped to code-level checks
- OWASP session management patterns
- Cookie security attributes (HttpOnly, Secure, SameSite)
- Magic link / passwordless patterns and their risks
- MFA requirements and implementation patterns
- For each control: "how to check in code" instructions

### Create if missing: `administrative-safeguards.md`
Extract from § 164.308 the requirements with direct code or system-design implications:
- § 164.308(a)(4) — Information Access Management: access provisioning/deprovisioning flows
- § 164.308(a)(6) — Security Incident Procedures: what incident logging should look like in code
- § 164.308(a)(7) — Contingency Plan: backup/restore procedures, what to verify in code
- § 164.308(a)(8) — Evaluation: periodic technical review requirements
For each: what an auditor should look for in a codebase.

---

## Step 5 — Write a research log

Create or overwrite `~/.claude/skills/hipaa-audit/references/update-log.md`:

```markdown
# HIPAA Skill Update Log

**Date:** <YYYY-MM-DD>

## Sources fetched successfully
- <URL> — <one line on what was extracted>

## Sources that failed
- <URL> — <HTTP status or error>

## Gaps identified
- <bullet list>

## Changes made
- <file> — <what was added or changed>

## Recommended follow-up
- <anything that couldn't be completed — paywalled content, PDFs that didn't parse, etc.>
```

---

## Constraints

- Only write to `~/.claude/skills/hipaa-audit/references/`
- Never modify `SKILL.md` or its frontmatter
- Only include content drawn from fetched sources — do not invent requirements
- Where a source failed to load, note it and skip rather than guessing
- Keep each reference file under 600 lines — split into a new file if needed