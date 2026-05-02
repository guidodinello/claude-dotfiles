---
name: meta-skill-security-audit-improver
description: >
  Improve and update the security-audit skill by fetching current OWASP cheat sheets, CWE Top 25,
  and NIST guidelines, then refreshing the three reference files with accurate, cited content.
  Use this skill when the user wants to refresh the security audit references, check if OWASP
  guidance has changed, or strengthen the skill with updated vulnerability patterns.
  Trigger phrases: "update the security audit skill", "refresh the security references",
  "improve the security skill", "run the security skill updater".
compatibility:
  tools:
    - WebFetch
  allowed_domains:
    - owasp.org
    - cheatsheetseries.owasp.org
    - cwe.mitre.org
    - pages.nist.gov
    - csrc.nist.gov
---

## What this skill does

Fetches authoritative OWASP, CWE, and NIST sources, compares them against the current reference
files, and updates those files with accurate, cited content.

Only modifies files inside `~/.claude/skills/security-audit/references/`. Never touches `SKILL.md`.

---

## Step 1 — Read current state

Before fetching anything, read every existing reference file:

```
~/.claude/skills/security-audit/SKILL.md
~/.claude/skills/security-audit/references/injection-patterns.md
~/.claude/skills/security-audit/references/auth-access-patterns.md
~/.claude/skills/security-audit/references/exposure-patterns.md
~/.claude/skills/security-audit/references/update-log.md
```

Note what each file covers, which patterns look thin, and what lacks an authoritative citation.

---

## Step 2 — Fetch authoritative sources

Fetch each URL below. Extract technically actionable content — named controls, specific detection
techniques, concrete fixes. Skip introductory summaries and marketing copy.

If a fetch fails, note it in the update log (Step 5) and continue — do not halt.

### OWASP Top 10 (fetch first — used to spot missing categories)

| URL | What to extract |
|-----|----------------|
| `https://owasp.org/Top10/` | Current Top 10 list with category names and brief descriptions — cross-check against reference files for any category not yet covered |

### Injection patterns — sources for `injection-patterns.md`

| URL | What to extract |
|-----|----------------|
| `https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html` | Parameterized query patterns, ORM-safe usage, second-order injection, stored procedure risks |
| `https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html` | Safe subprocess APIs, allowlist validation, shell=true risks, language-specific safe patterns |
| `https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html` | Open redirect patterns, safe redirect validation, allowlist approach |
| `https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html` | SSRF detection patterns, network-layer defenses, URL validation, metadata endpoint risks (169.254.169.254) |

### Auth & access control — sources for `auth-access-patterns.md`

| URL | What to extract |
|-----|----------------|
| `https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html` | Password requirements, account lockout thresholds, secure session creation, MFA guidance, credential stuffing defenses |
| `https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html` | Enforce on every request, deny-by-default, centralized authorization logic, IDOR prevention |
| `https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html` | SameSite cookie attributes, synchronizer token pattern, double-submit cookie, when Bearer auth makes CSRF moot |
| `https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Tokens_Cheat_Sheet_for_Java.html` | Algorithm pinning, key strength requirements, expiry best practices, token revocation patterns |
| `https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html` | Reset token entropy requirements, expiry windows, single-use enforcement, account enumeration prevention |
| `https://pages.nist.gov/800-63-3/sp800-63b.html` | Password length/complexity requirements, session management rules, authenticator assurance levels (AAL1/2/3), reauthentication triggers |

### Exposure & hardening — sources for `exposure-patterns.md`

| URL | What to extract |
|-----|----------------|
| `https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html` | Secret storage patterns, CI/CD secret handling, rotation requirements, scanning for committed secrets |
| `https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html` | What to log, what NOT to log (sensitive fields), log injection prevention, integrity requirements |
| `https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html` | Output encoding rules, CSP configuration, DOM XSS sources and sinks, trusted types |
| `https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html` | Current recommended header values, deprecated headers to remove, CSP directives |
| `https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html` | Approved algorithms, key sizes, IV/nonce requirements, password hashing algorithms and cost factors |
| `https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html` | Safe error response patterns, error ID correlation, what must never be returned to clients |

### CWE Top 25 (cross-reference for coverage gaps)

| URL | What to extract |
|-----|----------------|
| `https://cwe.mitre.org/top25/archive/2024/2024_cwe_top25.html` | Top 25 list with CWE IDs and names — identify any CWE not yet represented in any reference file |

---

## Step 3 — Gap analysis

After fetching, compare sources against the current reference files. Build a gap list:

- OWASP Top 10 categories with no corresponding patterns in any reference file
- CWE Top 25 entries with no detection technique documented
- OWASP cheat sheet guidance that contradicts or improves on existing patterns (e.g., updated hash cost factors, new SameSite recommendations)
- Patterns in the reference files with no authoritative citation
- Detection grep commands that are outdated or could be improved

In particular, check for:
- **SSRF** — currently absent from all three reference files (OWASP A10:2021)
- **Open redirect** — may be missing from `injection-patterns.md`
- **Rate limiting on auth endpoints** — likely thin in `auth-access-patterns.md`
- **Trusted types / DOM XSS sinks** — may be missing from XSS section in `exposure-patterns.md`

---

## Step 4 — Update reference files

### Always update: `injection-patterns.md`
- Add SSRF section if missing — include: what URLs to block (localhost, 169.254.169.254), how to detect user-controlled URL fetch calls, safe allowlist approach
- Add Open Redirect section if missing
- Add CWE IDs to each pattern header (e.g., "SQL Injection (CWE-89)")
- Verify detection grep commands compile and reflect current patterns

### Always update: `auth-access-patterns.md`
- Update NIST 800-63B password requirements if the fetched version differs
- Add Rate Limiting section for auth endpoints if missing — include: thresholds from OWASP auth cheat sheet, how to detect missing rate limiting in code
- Update JWT section with current algorithm recommendations
- Add CWE IDs to each pattern header

### Always update: `exposure-patterns.md`
- Update security headers table with any new recommended values from the HTTP Headers cheat sheet
- Update bcrypt cost factor recommendation if OWASP crypto cheat sheet specifies a new minimum
- Add Trusted Types / DOM XSS sink section to XSS entry if missing
- Add CWE IDs to each pattern header

### Create if missing: `ssrf-rce-patterns.md`
If SSRF and deserialization patterns are too large to fit cleanly into `injection-patterns.md`,
create a dedicated file covering:
- SSRF (CWE-918): detection, network-layer defenses, metadata endpoint risks
- Insecure Deserialization (CWE-502): detection in JSON/YAML/pickle/Java serialization, safe alternatives
- Code Injection via `eval`/`Function()`/`vm.runInContext()` (CWE-94)

Link to it from `injection-patterns.md` and from the `SKILL.md` Vulnerability Pattern Reference section (note this in the update log — SKILL.md itself is not modified by this meta-skill).

---

## Step 5 — Write an update log

Create or overwrite `~/.claude/skills/security-audit/references/update-log.md`:

```markdown
# Security Audit Skill — Update Log

**Date:** <YYYY-MM-DD>

## Sources fetched successfully
- <URL> — <one line on what was extracted or verified>

## Sources that failed
- <URL> — <HTTP status or error>

## Gaps identified
- <bullet list of patterns missing before this run>

## Changes made
- <file> — <what was added or changed, including old → new for any numeric values>

## CWE Top 25 coverage
- Covered: <CWE IDs now represented in reference files>
- Not yet covered: <CWE IDs with no corresponding pattern>

## Recommended follow-up
- <anything requiring manual verification or that couldn't be completed>
```

---

## Constraints

- Only write to `~/.claude/skills/security-audit/references/`
- Never modify `SKILL.md` or its frontmatter
- Only include content drawn from fetched sources — do not invent vulnerability details from training data
- Where a source failed to load, note it and skip rather than guessing
- Keep each reference file under 600 lines — if adding SSRF would exceed that, create `ssrf-rce-patterns.md` instead
- When updating numeric values (hash cost factors, key sizes, token entropy requirements), always note the old value → new value in the update log
