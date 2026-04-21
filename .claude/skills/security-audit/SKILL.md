---
name: security-audit
description: >
  Perform a comprehensive application security audit on a codebase. Use this skill whenever the
  user asks for a security review, vulnerability assessment, OWASP audit, or wants to find injection
  flaws, broken authentication, insecure data exposure, or access control weaknesses in application
  code. Also trigger when the user asks about SQL injection, XSS, CSRF, IDOR, secrets exposure,
  command injection, path traversal, or any OWASP Top 10 category. Do not wait for the user to say
  "security audit" explicitly — trigger whenever a vulnerability concern is raised about a codebase
  that handles user input or sensitive data.
---

## How to Run This Audit

Treat this as an adversarial simulation, not a checklist. Your job is to think like an attacker: map the attack surface, identify where user-controlled input reaches dangerous sinks, and find the gaps between what security controls exist and where they're actually enforced.

A control that exists in one middleware but is missing from one route is still a vulnerability.

---

## Step 0: Check for existing audit docs

Glob for `**/security*.md`, `**/SECURITY*.md`, `**/pentest*.md`, `**/vulnerability*.md`, `**/audit*.md` in the repo root and any `docs/` directories. If prior reports exist:

- Read them to understand what was already assessed and remediated
- Note which findings are marked REMEDIATED — do not re-raise these unless the fix appears incomplete or reverted
- Note any open recommendations not yet implemented — carry them forward
- If the prior doc conflicts with what you observe in code, flag the discrepancy explicitly

---

## Step 1: Orient yourself (do this before drawing any conclusions)

Run these discovery steps to map the full attack surface before evaluating any vulnerability.

**1. Find all entry points**
Glob for route definitions (`**/routes/**`, `**/api/**`, `**/handlers/**`, `**/controllers/**`). List every HTTP endpoint: method, path, and whether it sits behind an auth middleware. Public (unauthenticated) endpoints are the highest-priority attack surface — every one of them is reachable by an anonymous attacker.

**2. Find the auth system**
Grep for session creation (`jwt.sign`, `createSession`, `sign(`), middleware registration, and auth guard patterns. Determine: how are sessions issued and validated? Which routes are protected? Are there routes that should be protected but aren't? Is the guard applied at the router level or per-route (per-route is easier to miss)?

**3. Find all input ingestion points**
Grep for `req.params`, `req.query`, `req.body`, `req.headers`, `req.cookies`, and framework equivalents (e.g., `c.req.param()` in Hono, `event.pathParameters` in Lambda). Every one of these is attacker-controlled. Note which flow to: database queries, file paths, shell commands, HTML output, external API calls.

**4. Find the query layer**
Grep for raw SQL strings (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) and template literals containing SQL. Also grep for ORM query builders — identify where user input is passed to them. Parameterized queries and tagged template literals from the ORM are safe; string interpolation into SQL is not.

**5. Find external command execution**
Grep for `exec(`, `execSync(`, `spawn(`, `spawnSync(`, `child_process`, `shell: true`, `execFile`. Any of these that receive user-controlled input without sanitization is a command injection risk.

**6. Find file system access**
Grep for `readFile(`, `writeFile(`, `createReadStream(`, `path.join(`, `path.resolve(`, `fs.`. Where paths are constructed from user input, check for path traversal (`../` sequences bypassing a base directory).

**7. Find HTML rendering and output**
Grep for `dangerouslySetInnerHTML`, `innerHTML =`, `document.write(`, `v-html`, server-side template engines, and string concatenation into HTML. Where user content is inserted without encoding, XSS is possible.

**8. Find secrets and credentials**
Grep for hardcoded patterns: `sk_`, `pk_`, `AKIA`, `ghp_`, `-----BEGIN`, `postgres://`, `mysql://`. Also check `.env` files for accidental commits, and grep for API keys in comments and test fixtures.

**2a. Verify production call sites before assigning CRITICAL or HIGH**
For every vulnerable pattern found, before assigning severity, verify the function or handler is actually called in production code. Grep for its name, explicitly excluding test files (`**/__tests__/**`, `**/*.test.ts`, `**/*.spec.ts`, `**/*.test.tsx`):
- Callers only in tests: downgrade to MEDIUM, note "no production callers — latent risk only", recommend deletion rather than patching.
- No callers at all: same treatment.
- Production callers confirmed: proceed with original severity.

Dead code cannot be CRITICAL — a CRITICAL rating implies the attack path is reachable today.

---

## Attack Surface Map

The attack surface has three dimensions to keep in mind:

**Input sources** (attacker-controlled):
`req.params`, `req.query`, `req.body`, `req.headers`, `req.cookies`, URL path segments, file uploads, WebSocket messages, webhook bodies (before signature verification), OAuth callback parameters

**Dangerous sinks** (where bad input causes harm):
- DB query construction → SQL/NoSQL injection
- Shell command construction → command injection
- File path construction → path traversal / arbitrary file read
- HTML rendering → XSS
- `eval()`, `Function()`, `vm.runInContext()` → code injection
- Redirect targets → open redirect
- Server-side fetch with user-controlled URL → SSRF
- Object deserialization → prototype pollution / RCE

**Controls to verify coverage on:**
Auth middleware, input validation/sanitization schema, parameterized queries, output encoding, CSRF tokens, rate limiting, security headers, signature verification on webhooks

---

## Vulnerability Pattern Reference

See the following reference files for the full catalog of vulnerability patterns, with detection techniques and concrete fixes:

- [`references/injection-patterns.md`](references/injection-patterns.md) — SQL injection, command injection, path traversal, mass assignment, prototype pollution
- [`references/auth-access-patterns.md`](references/auth-access-patterns.md) — Missing auth, IDOR, privilege escalation, CSRF, JWT weaknesses, broken account management
- [`references/exposure-patterns.md`](references/exposure-patterns.md) — Hardcoded secrets, sensitive data in logs/URLs, XSS, security headers, information disclosure, weak crypto

---

## Investigative Methodology

### Follow the input, not the file structure

Pick a user-controlled value (e.g., `req.params.id`, `req.body.email`) and trace it forward:
- Does it flow into a SQL query? Is it parameterized or interpolated?
- Does it flow into a file path? Is it validated against a base directory?
- Does it flow into HTML output? Is it encoded?
- Does it flow into an external HTTP call? Is it validated?

Pick an authenticated endpoint and trace it end to end:
auth check → input validation → DB query → response serialization → client rendering → side effects

Pick a public endpoint (no auth) and ask: what is the worst thing an anonymous attacker can do by sending crafted input?

### Find the gap between stated controls and actual coverage

When you find a security control (auth middleware, input validator, parameterized query helper):
- Grep for every place it is applied
- Grep for every place it *should* be applied but isn't
- Never conclude "injection is mitigated" from seeing parameterized queries in some paths — verify every path that touches user input
- Inconsistency is a finding even if the control exists

### Think in attack chains, not isolated findings

A MEDIUM-severity IDOR combined with a MEDIUM-severity missing rate limit can form a CRITICAL attack chain (enumerate all user IDs in seconds). A LOW-severity information disclosure (stack traces in errors) combined with a MEDIUM-severity injection can reduce exploit complexity from HIGH to LOW. Note these combinations explicitly when you find them.

---

## Reporting Format

### Document header

Start every report with:

```markdown
# Application Security Audit

**System:** <app name>
**Date:** <YYYY-MM-DD>
**Auditor:** Claude Code (<model id>)
**Scope:** <what was covered — e.g. "Full static analysis — injection sinks, authentication, authorization, secrets, client-side security, API surface">
```

### Overall Assessment

Follow the header with a 2–4 sentence executive summary: what the system handles well, where the highest-risk gaps concentrate, and the single most important action. This is what a non-technical stakeholder reads first.

### Attack Surface Map

Before any findings, include:
1. An **Entry Points** table: route, method, auth required (YES/NO), notes
2. A **User Input → Dangerous Sinks** table: input source, sink type, location, sanitized (YES / NO / PARTIAL)

### Findings

Group findings under severity headings. Use sequential IDs so the remediation table can reference them.

```markdown
### CRITICAL
**C-1: <short title>**
- Location: `path/to/file.ts:line`
- Finding: What you observed
- Risk: The specific attack this enables (e.g., "An unauthenticated attacker can exfiltrate all patient records by sending a crafted SQL payload in the `q` query parameter")
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
- **CRITICAL** — Directly exploitable by an unauthenticated or low-privilege attacker; could result in data breach, RCE, full auth bypass, or cross-user data exposure. Reachable in production today. **Dead code cannot be CRITICAL** — if the vulnerable path has no production callers (verified via grep excluding tests), cap severity at MEDIUM.
- **HIGH** — Exploitable but requires specific conditions (authenticated attacker, chaining with another issue, specific browser/environment); significant risk of data exposure or privilege escalation.
- **MEDIUM** — Vulnerability exists but has meaningful mitigating factors; will compound over time or escalate to HIGH under changed conditions. Latent risk in dead code belongs here.
- **LOW** — Defense-in-depth gaps; hardening issues that don't represent a direct exploit path today.
- **INFO** — Two uses: (1) observations that cannot be assessed from static analysis alone (runtime config, WAF rules, cloud IAM policies, third-party SLA); (2) **positive controls** — things the codebase does correctly. Prefix positive controls with "Positive control —".

Do not put "What's Working Well" in a separate section. Positive controls belong in `### INFO` as `I-*` findings — this keeps all observations in one place and makes strengths feel as deliberate as gaps.

### Prioritized Remediation

Use consistent effort estimates so items are comparable:

| Label | Meaning |
|---|---|
| Tiny | < 30 min — a one-liner, a config flag, a header |
| Small | 30 min – 2 hr — a single function, a middleware addition |
| Medium | 2–8 hr — a validation layer, a schema change, cross-service fix |
| Large | 1–3 days — auth redesign, architectural change |
| XL | > 3 days — multi-sprint, requires staged rollout |

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

### Sources Cited

End with a **Sources** section listing every external reference used — OWASP articles, CVE advisories, framework security docs. No citation, no claim about external behavior.

```markdown
## Sources

- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [OWASP Top Ten 2021](https://owasp.org/www-project-top-ten/)
```

### Key Files Reference

End with a two-column table mapping file paths to their security-relevant purpose. This helps engineers navigate to the right place when acting on findings.
