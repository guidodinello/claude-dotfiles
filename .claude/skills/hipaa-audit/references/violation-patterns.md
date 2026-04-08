# HIPAA Violation Patterns

Anti-patterns to hunt for regardless of stack.

---

## Logging Violations

- PHI appearing in log statements at any level (debug, info, warn, error)
  - Check: `logger.debug(patient)`, `console.log(req.body)` on PHI endpoints, error wrapping patient objects
- PHI in error messages returned to clients (e.g., `"Patient john@example.com not found"`)
- PHI in exception stack traces (object toString includes PHI fields)
- PHI in HTTP access logs via URL query parameters (e.g., `/search?email=patient@example.com`)

**How to check:** Grep every logging call on PHI-handling code paths. Check if objects are spread or serialized before logging. Find the central logger and verify redaction middleware is applied.

---

## Storage Violations

- PHI in `localStorage` or `sessionStorage` (readable by any JS on the page, persists after tab close)
- PHI in cookies without `HttpOnly` flag (readable by JS) or without `Secure` flag (sent over HTTP)
- PHI in browser-side caches (service workers, cache API) without expiry
- PHI in temporary files without cleanup (e.g., file uploads buffered to disk)
- Unencrypted PHI at rest in databases without column-level or disk-level encryption
- PHI in application caches (Redis, Memcached) without TTL or encryption

**How to check:** Grep for `localStorage.setItem`, `sessionStorage.setItem`, cookie-setting code. Review file upload handlers. Check ORM models for fields that store PHI and whether encryption is applied.

---

## Transmission Violations

- PHI sent over HTTP instead of HTTPS
- PHI in URL path segments or query parameters (logged by proxies, CDNs, browser history)
  - Correct: `POST /patients/{id}/records` with PHI in body
  - Wrong: `GET /patients?ssn=123-45-6789`
- PHI in email bodies via a provider without a BAA
- PHI in SMS messages via a provider without a BAA
- Webhooks accepting PHI without verifying the payload signature before processing
- API responses that return more PHI than necessary (over-fetching; role doesn't need all fields)

**How to check:** Find all external HTTP calls. Check URL construction. Find email/SMS send calls and identify the provider. Find inbound webhook handlers and check for signature verification before payload access.

---

## Access Control Violations

- Endpoints that return PHI without any authentication check
- IDOR: Patient A can access Patient B's records by manipulating an ID in the URL or request body
  - Check: every query fetching patient data — does it enforce `WHERE patient_id = $authenticated_id`?
- Staff roles with broader PHI access than their job requires (violates minimum necessary standard)
- No session expiry, or session TTL longer than 8 hours on PHI-bearing systems
- Automatic logoff not implemented (addressable, but flag if absent with no documented alternative)
- Shared service account credentials used to access PHI (breaks the audit trail — cannot attribute access to an individual)
- Missing authorization on internal APIs (e.g., a microservice endpoint that trusts any caller)

**How to check:** Identify every route that touches PHI. Trace its middleware chain — is auth applied? Is the result filtered to only the authenticated user's data? Find session TTL configuration.

---

## Audit Trail Violations

- PHI accessed (read or written) with no audit log event
  - Minimum to log: who (user ID), what (record accessed, operation type), when (timestamp), from where (IP or source system)
- Audit logs stored in the same database as application data (can be altered by an attacker who gains DB access)
- Audit log records that can be deleted or updated by application code
- No defined retention policy (HIPAA requires 6 years minimum for audit documentation)
- Bulk exports of PHI (reports, data downloads) with no audit event
- Failed access attempts not logged (important for detecting probing/IDOR attempts)

**How to check:** Find the audit log mechanism. Check if every PHI endpoint calls it. Check where audit logs are written (same DB? separate table? append-only?). Grep for any delete/update operations against the audit log table.

---

## Secrets and BAA Violations

- API keys to PHI-handling vendors stored in code, `.env` files checked into version control, or client-side bundles
- Vendors that receive PHI without a signed BAA (cannot be verified from code — flag as INFO for human review)
- Third-party error monitoring receiving PHI in error payloads
  - Sentry: check if `beforeSend` scrubs PHI from error events
  - Datadog APM: check if trace data includes PHI in span attributes
  - Any analytics SDK: check what events are tracked and what properties are sent
- Webhook secrets hardcoded or stored insecurely
- Overly permissive vendor API keys (should be scoped to minimum necessary access)

**How to check:** Grep for SDK instantiations of monitoring/analytics tools. Find their configuration and check for scrubbing/filtering. Search for hardcoded secrets in the codebase. Check `.gitignore` for `.env` exclusion.
