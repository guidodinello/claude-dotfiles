# HIPAA Violation Patterns

Anti-patterns to hunt for regardless of stack. Organized by the Security Rule's technical safeguard categories (45 CFR § 164.312) plus Privacy Rule obligations that have direct code implications.

---

## 1. Access Control Violations (§ 164.312(a))

### Unique user identification (Required)

-   Shared credentials or service accounts used to access ePHI — breaks the audit trail because you can't attribute access to an individual
-   Staff roles with broader PHI access than their job function requires (violates minimum necessary standard — see section 7)
-   Missing authorization checks on internal APIs or microservice endpoints that trust any caller on the internal network

### Automatic logoff (Addressable)

-   No session expiry, or session TTL longer than 8 hours on PHI-bearing systems without compensating controls
-   Inactivity timeout not implemented or only implemented client-side (server must invalidate the session, not just redirect)
-   No "logout from all devices" / session revocation when credentials are compromised

### IDOR (Insecure Direct Object Reference)

-   Patient A can access Patient B's records by manipulating an ID in the URL or request body
-   Check: every query fetching patient-scoped data must enforce `WHERE patient_id = $authenticated_session_id`, not trust a caller-supplied ID
-   Check: bulk list endpoints must scope results to the authenticated user's organization/role

**How to check:** Find every route that returns ePHI. Trace its middleware chain — is auth applied? Is the result scoped to the authenticated user's data? Look for any query that accepts an ID from the request without cross-checking it against the session.

---

## 2. Audit Controls (§ 164.312(b))

This standard has no implementation specifications — it is a Required standard with full flexibility in implementation. The requirement: implement hardware, software, or procedural mechanisms that record and examine ePHI access activity.

### Missing audit events

-   PHI read (GET patient record, prescription, order, lab result) with no audit log entry
-   PHI written or updated with no audit log entry
-   PHI deleted or archived with no audit log entry
-   Bulk export or report containing PHI with no audit log entry
-   Failed access attempts not logged (important for detecting IDOR probing)
-   Magic link generation and use not logged
-   Staff login and logout not logged

### Incomplete audit records

-   Audit records missing any of: user ID, action type, resource type, resource ID, timestamp, source IP
-   Shared service account used — impossible to attribute to an individual (also an Access Control violation)

### Audit log integrity risks

-   Audit logs stored in the same database as application data — an attacker with DB write access can alter them
-   Application code has a DELETE or UPDATE path against the audit log table — logs must be append-only
-   No defined retention period (HIPAA: 6 years minimum for security documentation; best practice is to apply the same to audit logs)

**How to check:** Find the audit log mechanism. Map every PHI endpoint against it — is the log call present on every read and write path? Check whether the audit log table has any delete/update routes in the codebase.

---

## 3. Integrity Controls (§ 164.312(c))

The requirement: implement policies and procedures to protect ePHI from improper alteration or destruction.

### Hard deletes on PHI tables

-   `DELETE FROM patients` or equivalent instead of soft-delete (`archived_at`, `deleted_at`) — hard deletes make it impossible to detect unauthorized destruction
-   Check: does every PHI table use soft-delete? Is there any code path that issues a hard delete on patient records, orders, prescriptions, or lab results?

### No protection against unauthorized modification

-   PHI fields that can be updated without an audit trail — an insider could alter a patient's diagnosis or medication record with no record of the change
-   No checksums or version history on critical ePHI fields (weight, medication, lab results)

### Transmission integrity (Addressable)

-   No TLS on connections between internal services that carry ePHI (e.g., backend-to-database, backend-to-pharmacy API)
-   TLS version below 1.2 — flag as HIGH
-   Self-signed certificates in production without validation — allows MITM

**How to check:** Grep for `DELETE FROM` or ORM `.destroy()` / `.delete()` calls on PHI tables. Confirm soft-delete is the standard pattern. Check TLS configuration on external API calls.

---

## 4. Person or Entity Authentication (§ 164.312(d))

This is a standalone Required standard that is often overlooked. The requirement: implement procedures to verify that a person or entity seeking access to ePHI is the one claimed.

This goes beyond session management — it covers how the system establishes identity in the first place.

### Weak authentication mechanisms

-   No MFA on staff accounts with access to ePHI — single-factor (password only) is increasingly considered insufficient for HIPAA systems, though not explicitly required by the rule
-   Magic links sent to unverified email addresses — if email ownership is not established, the link doesn't authenticate the patient
-   Password reset flows that don't verify identity before issuing a new credential
-   No account lockout or rate limiting on login/magic-link endpoints

### Token security

-   Session tokens or magic link tokens that are predictable or not cryptographically random
-   Tokens not invalidated after use (magic links must be single-use)
-   Tokens with excessive TTL (magic links: 15 minutes max; staff sessions: 8 hours is the practical ceiling for HIPAA-adjacent systems)
-   Tokens stored in localStorage (readable by any JS on the page; use HttpOnly cookies)

### Cookie security

-   Session cookie missing `HttpOnly` flag — readable by JS
-   Session cookie missing `Secure` flag — sent over HTTP
-   Session cookie missing `SameSite` — CSRF risk
-   CSRF protection absent on mutating endpoints that touch ePHI

**How to check:** Find session/token creation code. Check cookie attributes. Check magic link TTL and single-use enforcement. Find login and magic-link endpoints and verify rate limiting is applied.

---

## 5. Transmission Security (§ 164.312(e))

### PHI in transit unencrypted or weakly encrypted

-   PHI sent over HTTP (not HTTPS) — flag as CRITICAL
-   TLS below 1.2 — flag as HIGH
-   PHI in URL query parameters — logged by proxies, CDNs, browser history, and server access logs even over HTTPS
    -   Correct: `POST /patients/{id}/records` with PHI in body
    -   Wrong: `GET /search?email=patient@example.com`

### PHI transmitted to vendors without BAA

-   Email bodies containing PHI sent via a provider without a BAA (SendGrid, Mailgun, Postmark — must confirm BAA)
-   SMS messages containing PHI via a provider without a BAA (Twilio, Vonage)
-   Webhook payloads containing PHI sent to an unauthenticated or unverified endpoint

### Inbound webhook security

-   Webhook handlers that parse and trust the payload before verifying the signature
-   Signature verification logic that has a bypass: e.g., returns `valid: true` when the secret env var is not configured
-   No replay protection on webhooks (missing `timestamp` check on signed payloads)

**How to check:** Find all external HTTP calls. Check URL construction — is PHI ever in the path or query string? Find inbound webhook handlers and trace the order of operations: is signature checked before payload is read?

---

## 6. Logging Violations

These are the most common code-level HIPAA violations because they're easy to introduce accidentally.

-   PHI appearing in log statements at any level (debug, info, warn, error)
    -   Common patterns: `logger.debug(patient)`, `console.log(req.body)` on PHI endpoints, `logger.error(err)` where `err` wraps a patient object
-   PHI in error messages returned to clients (e.g., `"Patient john@example.com not found"`)
-   PHI in exception stack traces (object toString includes PHI fields)
-   PHI in HTTP access logs via URL query parameters — these are often logged by the web server, CDN, or load balancer even if application logs redact them

**How to check:** Find the central logger. Verify PHI redaction middleware is applied and covers all known PHI field names. Then grep every logging call on PHI-handling code paths — check if objects are spread or serialized before logging. Don't stop at the logger: check that the redaction runs before the log call, not after.

---

## 7. Minimum Necessary Standard (Privacy Rule § 164.502(b))

This is a Privacy Rule requirement, not Security Rule, but it has direct code implications. The requirement: limit uses and disclosures of PHI to the minimum necessary to accomplish the intended purpose.

In code, this means:

### API responses returning more PHI than the caller's role needs

-   A staff role with read-only access receiving the same patient payload as an admin
-   A list endpoint returning full patient objects when only IDs and names are needed for the UI
-   A pharmacy API call receiving the patient's full profile when only name, DOB, and medication are needed

### Frontend rendering PHI it shouldn't have

-   Client-side code receiving a full patient object and only displaying two fields — the rest is in the browser's memory and can be extracted
-   Bulk data loaded into the frontend for client-side filtering — filter server-side and return only what's displayed

### Third-party integrations receiving excess PHI

-   An analytics or error monitoring tool receiving full patient objects in event payloads when only a session ID is needed
-   A support tool (e.g., Intercom) receiving diagnosis or medication fields when only the patient's name and email are needed for support context

**How to check:** For each API endpoint returning ePHI, check what fields are included in the response vs. what fields the calling role actually needs. For third-party integrations, check what data is passed in event tracking calls, error payloads, and support tool identify calls.

---

## 8. Secrets and BAA Violations

### Insecure credential storage

-   API keys to PHI-handling vendors stored in code, `.env` files checked into version control, or client-side bundles
-   Secrets stored as plain environment variables in a hosting platform instead of a secrets manager (Cloudflare Secrets, AWS Secrets Manager, etc.)
-   Webhook secrets hardcoded in source code

### Third-party tools receiving PHI without BAA

-   Error monitoring (Sentry, Datadog, Rollbar) receiving PHI in error payloads
    -   Sentry: check for `beforeSend` hook scrubbing PHI from error events
    -   Datadog APM: check span/trace attributes for PHI; DB query parameters in traces can contain PHI
-   Analytics tools (Mixpanel, Segment, Amplitude, Heap) — check every `.track()` / `.identify()` call for PHI in event properties
-   Support tools (Intercom, Zendesk) receiving diagnosis, medication, or other clinical PHI fields

**How to check:** Grep for SDK instantiations of monitoring/analytics tools. Find their configuration and check for scrubbing/filtering. Search for hardcoded secrets. Check `.gitignore` for `.env` exclusion.

---

## Quick Reference: Required vs Addressable

| Standard | Specification | Required / Addressable |
|---|---|---|
| Access Control | Unique user identification | Required |
| Access Control | Emergency access procedure | Required |
| Access Control | Automatic logoff | Addressable |
| Access Control | Encryption/decryption at rest | Addressable |
| Audit Controls | Record/examine ePHI activity | Required (no specs) |
| Integrity | Protect from alteration/destruction | Required |
| Integrity | Transmission integrity (checksums) | Addressable |
| Person/Entity Authentication | Verify identity of accessor | Required (no specs) |
| Transmission Security | Guard against unauthorized access in transit | Required |
| Transmission Security | Encryption in transit | Addressable |

"Addressable" means: implement it, OR document why it's not reasonable/appropriate AND implement an equivalent alternative. It does not mean optional.
