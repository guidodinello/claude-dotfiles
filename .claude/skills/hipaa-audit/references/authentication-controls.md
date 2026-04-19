# Authentication Controls Reference

Reference for auditing authentication, session management, and access verification in HIPAA-covered systems.

Sources:
- 45 CFR § 164.312(d) — Person or Entity Authentication (Required)
- 45 CFR § 164.312(a)(2)(iii) — Automatic Logoff (Addressable)
- 45 CFR § 164.312(a)(2)(iv) — Encryption/Decryption (Addressable)
- NIST SP 800-63B-4 (Digital Identity Guidelines: Authentication and Authenticator Management,
  April 2024 — current version supersedes Rev 3)
  https://csrc.nist.gov/pubs/sp/800/63/b/4/final
- OWASP Session Management Cheat Sheet
  https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Access Control Cheat Sheet
  https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html

---

## § 164.312(d) — Person or Entity Authentication

**Designation:** Required (no implementation specifications — full flexibility in implementation)

**Regulatory text:** Implement procedures to verify that a person or entity seeking access to
electronic protected health information is the one claimed.

**What this means for code review:**

This standard requires that the system establish *who* is accessing ePHI before granting access,
and that the identity claim is verified — not just asserted. It is not satisfied by a session
cookie alone if that cookie was obtained without verifying the claimed identity.

### How to check in code

1. Find every entry point to ePHI (routes, API endpoints, background jobs that process patient
   records).
2. For each: trace back to the authentication mechanism. Is there a verified identity before
   ePHI is accessed? Or does the system trust a cookie/token without confirming it maps to a
   real, current user?
3. Find session creation code: what verification must succeed before a session is created?
4. Find password reset and magic link flows: does identity verification occur before a new
   credential is issued?

---

## § 164.312(a)(2)(iii) — Automatic Logoff

**Designation:** Addressable

**Regulatory text:** Implement electronic procedures that terminate an electronic session after
a predetermined time of inactivity.

**What this means for code review:**

Server-side session invalidation after inactivity. Client-side redirect is not sufficient —
if the server doesn't invalidate the session token, a client-side redirect can be bypassed.

### How to check in code

- Find session storage mechanism (DB table, Redis, JWT). Does the session record have an
  `expires_at` or equivalent?
- For JWT: is the `exp` claim enforced server-side? JWTs without short expiry and server-side
  revocation cannot implement automatic logoff.
- Is the TTL configured? Where? Grep for the value — is it appropriate?
- Is there a "last activity" timestamp that resets the inactivity clock? Or is it a fixed-time
  expiry regardless of activity?
- Is there a path to terminate all sessions for a user (credential compromise response)?

---

## NIST SP 800-63B-4 Password Requirements

NIST SP 800-63B-4 is the current version (April 2024). Rev 3 is withdrawn.

### Memorized Secret (Password) Requirements

| Requirement | Single-factor auth | MFA (password is one factor) |
|---|---|---|
| Minimum length | 15 characters | 8 characters |
| Maximum length | At least 64 characters | At least 64 characters |
| Composition rules | SHALL NOT impose (no required uppercase, numbers, symbols) | Same |
| Breach list check | SHALL compare against known-compromised passwords | Same |
| Mandatory rotation | SHALL NOT require arbitrary periodic rotation | Same |

**Breach list check** — when a user sets or changes a password, the system must compare it
against a list of known-compromised values. This includes: previously breached passwords,
dictionary words, repetitive sequences (e.g., "aaaaaa"), context-specific words (username,
service name).

### How to check in code

- Find the password validation function. Does it enforce a minimum length of 15 (or 8 for MFA)?
- Does it reject passwords found in a breach corpus (e.g., via HaveIBeenPwned API or local list)?
- Does it impose unnecessary complexity rules (uppercase+number+symbol required)? Flag if so —
  this diverges from NIST guidance and often leads to weaker passwords in practice.
- Does it force periodic password rotation? Flag if so — NIST says don't.
- Is there a maximum length cap below 64? Flag as non-compliant.

---

## NIST SP 800-63B-4 Authenticator Assurance Levels (AALs)

AAL defines the strength of the authentication transaction. Higher AAL = stronger assurance.
For HIPAA systems handling ePHI, AAL2 is the practical minimum for staff accounts.

### AAL1
- Single-factor or multi-factor authentication
- Session reauthentication: overall timeout ≤ 30 days
- Acceptable authenticators: passwords, OTP devices, single-factor cryptographic

### AAL2
- Multi-factor authentication required
- Must offer a phishing-resistant authentication option
- Session reauthentication: overall timeout ≤ 24 hours; inactivity timeout ≤ 1 hour
- When inactivity timeout fires (but overall timeout hasn't): may reauthenticate with only
  password or biometric + session secret (reduced to single-factor re-check)
- Acceptable authenticators: TOTP apps, hardware security keys (FIDO2), smart cards

### AAL3
- Requires hardware-based authenticator + verifier impersonation resistance (phishing resistant)
- Session reauthentication: overall timeout ≤ 12 hours; inactivity timeout ≤ 15 minutes
- Requires proof of possession of a key through a cryptographic protocol

### HIPAA mapping

| Account type | Recommended AAL | Session timeout |
|---|---|---|
| Staff with ePHI access | AAL2 minimum | ≤ 24 hours overall, ≤ 1 hour idle |
| Admin / privileged | AAL2 or AAL3 | ≤ 24 hours overall, ≤ 1 hour idle |
| Patient portal (low-risk) | AAL1 | ≤ 30 days |
| Patient portal (clinical access) | AAL2 recommended | ≤ 24 hours overall, ≤ 1 hour idle |

### How to check in code

- Find session TTL configuration. Does it match the AAL requirements above?
- Is idle timeout implemented server-side (last-activity timestamp checked on each request)?
- For staff accounts: is MFA enforced? Where? Grep for MFA bypass paths — does any role or
  endpoint skip MFA?
- Is a phishing-resistant option (FIDO2 / hardware key) offered at AAL2?

---

## OWASP Session Management Requirements

Source: OWASP Session Management Cheat Sheet

### Session ID Properties

- **Entropy:** Session IDs must be cryptographically random with at least 128 bits of entropy.
  Predictable session IDs (sequential integers, timestamp-based) are HIGH severity.
- **Length:** At least 128 bits (16 bytes) is the OWASP minimum. Shorter IDs are guessable.
- **Generation:** Use a cryptographically secure random number generator (CSPRNG), not
  `Math.random()` or similar.

### Cookie Security Attributes

The most secure session cookie configuration (per OWASP):

```
Set-Cookie: __Host-SID=<session token>; path=/; Secure; HttpOnly; SameSite=Strict
```

| Attribute | Effect | Absence risk |
|---|---|---|
| `HttpOnly` | Prevents JavaScript from reading the cookie | XSS can steal session token |
| `Secure` | Cookie only sent over HTTPS | Session token sent over HTTP |
| `SameSite=Strict` | Cookie not sent on cross-origin requests | CSRF risk |
| `SameSite=Lax` | Cookie sent on top-level navigation cross-origin | Weaker CSRF protection |
| `__Host-` prefix | Enforces Secure, path=/, and no Domain attribute | Defense in depth |

**Do not set `Domain` attribute broadly** (e.g., `.example.com`) — this shares the cookie
across all subdomains, widening the attack surface.

### Session Fixation Prevention

After any authentication event (login, MFA completion, privilege change), regenerate the
session ID. The old session ID must be invalidated.

**How to check:** Find the session creation call. Is it invoked after login completes (not
before)? Or does the same session ID persist across the authentication state change?

### Concurrent Sessions

Flag whether the system permits multiple simultaneous sessions per user. For staff accounts on
HIPAA systems: concurrent sessions increase the risk of undetected shared credential use.

### Logout

Logout must invalidate the session server-side. Deleting the cookie client-side without
server-side revocation leaves the session valid if the token is captured.

**How to check:** Find the logout handler. Does it delete the session record from the
server-side store? Or does it only clear the client cookie?

---

## Cookie Security Audit Checklist

For each session cookie found in the codebase:

```
[ ] HttpOnly flag set
[ ] Secure flag set
[ ] SameSite=Strict or Lax set (Strict preferred for PHI systems)
[ ] No overly broad Domain attribute
[ ] path=/ or appropriately scoped
[ ] Session ID is cryptographically random (CSPRNG)
[ ] Session ID is at least 128 bits / 16 bytes
[ ] Session TTL enforced server-side (not just client-side expiry)
[ ] Inactivity timeout resets on activity; server-side check on each request
[ ] Session invalidated server-side on logout
[ ] Session ID regenerated after login / MFA completion
```

---

## Magic Link / Passwordless Patterns

Magic links (one-time email links) are common in patient portals. They carry specific risks.

### Requirements

- **Single-use:** The token must be invalidated immediately after first use. A reused magic
  link is equivalent to a reused session token.
- **Short TTL:** Maximum 15 minutes. Longer TTLs leave the link in email servers, forwardable,
  and accessible to anyone with inbox access.
- **Cryptographically random:** The token must be generated with a CSPRNG. A short or
  sequential token is guessable.
- **Email ownership baseline:** Magic links only authenticate identity if the email account
  itself is secured. Unverified email addresses weaken the guarantee.

### How to check in code

- Find magic link generation code. What is the token length? How is it generated?
- Find token validation code. Is the token deleted/invalidated after first use?
- What is the TTL? Grep for the expiry value.
- Is there rate limiting on magic link generation? (Prevents abuse as a DoS or enumeration tool)
- What happens if the same token is submitted twice? Should return invalid/expired.

---

## Multi-Factor Authentication (MFA) Implementation Patterns

### What to look for

- **Enforcement boundary:** Where is MFA checked? Is it in middleware (applied to all PHI
  routes), or per-route (risks gaps)?
- **Bypass paths:** Find every authentication code path. Is there a development flag, admin
  override, or IP-based exemption that bypasses MFA? Each bypass is a finding.
- **Factor types:** TOTP (time-based OTP apps) satisfies AAL2. SMS-based OTP is weaker (SIM
  swap risk) — acceptable as addressable measure but note the risk.
- **Recovery codes:** If recovery codes exist (for lost authenticator), they must be single-use
  and cryptographically random. Recovery code usage must trigger an audit log entry.

### How to check in code

```
1. Grep for MFA check function / middleware
2. Map every route that returns or modifies ePHI
3. Verify MFA check is applied to all of them
4. Search for any conditional that skips MFA (env var, IP check, admin flag)
5. Find recovery code generation and validation — are they single-use?
6. Confirm MFA events are in the audit log
```
