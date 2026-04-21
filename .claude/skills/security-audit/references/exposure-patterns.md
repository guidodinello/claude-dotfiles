# Exposure Patterns Reference

Catalog of vulnerability patterns related to sensitive data exposure, client-side security, and security hygiene. These often serve as force multipliers for other vulnerabilities.

---

## Hardcoded Secrets and Credentials

**Pattern:** API keys, database credentials, JWT secrets, or private keys embedded directly in source code.

```ts
// UNSAFE — hardcoded in source
const JWT_SECRET = "my-super-secret-key-123";
const stripe = new Stripe("sk_live_abc123xyz...");
const db = new Client({ password: "postgres_prod_pass" });

// UNSAFE — committed .env file or config with real values
// .env.production included in git history
DATABASE_URL=postgres://user:realpassword@prod-host/db
```

**Risk:** Anyone with read access to the repository (including historical git history) can extract production credentials. Severity: CRITICAL for credentials that grant DB access, CRITICAL for private keys, HIGH for third-party API keys that access sensitive data.

**Detection:**
```bash
# Stripe-style keys
grep -rn 'sk_live_\|sk_test_\|pk_live_\|pk_test_' src/

# AWS keys
grep -rn 'AKIA[0-9A-Z]\{16\}' src/

# GitHub tokens
grep -rn 'ghp_\|gho_\|github_pat_' src/

# Private keys
grep -rn '-----BEGIN.*PRIVATE KEY-----' src/

# Database URLs with embedded credentials
grep -rn 'postgres://\|mysql://\|mongodb://' src/

# Generic patterns (review false positives)
grep -rn 'SECRET\s*=\s*["'"'"'][^$]' src/
grep -rn 'PASSWORD\s*=\s*["'"'"'][^$]' src/
grep -rn 'API_KEY\s*=\s*["'"'"'][^$]' src/

# Check git history for secrets ever committed
git log --all --full-history --diff-filter=A -- '*.env' '*.env.*'
```

**Fix:**
- Move all secrets to environment variables. Never commit `.env` files with real values.
- Add `.env`, `.env.local`, `.env.production` to `.gitignore`.
- If a secret was ever committed (even if later removed), treat it as compromised and rotate immediately — it remains in git history.
- Use a secrets manager in production (Cloudflare Secrets, AWS Secrets Manager, HashiCorp Vault).

---

## Sensitive Data in Logs

**Pattern:** User PII, PHI, tokens, or passwords logged at any level (debug, info, error).

```ts
// UNSAFE — logging the full request body (may include passwords, SSNs, etc.)
logger.info("Processing request", { body: req.body });

// UNSAFE — error includes the user object
logger.error("Update failed", { error, user });

// UNSAFE — token in log
logger.debug("Auth token", { token: req.headers.authorization });

// UNSAFE — object spread leaks nested sensitive fields
console.log("Patient updated", { ...patient }); // includes dob, ssn, etc.
```

**Risk:** Logs are often stored in third-party services (Datadog, Sentry, CloudWatch), retained for extended periods, and accessible to a wider audience than the DB. PHI or credentials in logs is a breach vector and in healthcare a HIPAA violation. Severity: HIGH.

**Detection:**
```bash
# Logging calls with potentially sensitive data
grep -rn 'console\.log\|logger\.\(info\|debug\|error\|warn\)' src/ | grep -i 'body\|password\|token\|patient\|user\|phi'

# Object spreads in log calls
grep -rn 'console\.log.*\.\.\.' src/
grep -rn 'logger\..*\.\.\.' src/
```

**Fix:** Redact sensitive fields before logging. Define an explicit allowlist of loggable fields rather than logging full objects.

```ts
function sanitizeForLog(obj: Record<string, unknown>) {
  const SENSITIVE = new Set(["password", "token", "ssn", "dob", "authorization"]);
  return Object.fromEntries(
    Object.entries(obj).map(([k, v]) => [k, SENSITIVE.has(k) ? "[REDACTED]" : v])
  );
}

logger.info("Request received", { body: sanitizeForLog(req.body) });
```

---

## Sensitive Data in URLs

**Pattern:** Tokens, passwords, session IDs, or PII placed in URL query parameters.

```ts
// UNSAFE — token in query param lands in server logs, browser history, Referer headers
res.redirect(`/reset-password?token=${resetToken}`);
app.get("/export?patientId=${id}&ssn=${ssn}", handler);

// UNSAFE — session token in URL
const magicLink = `${BASE_URL}/login?token=${sessionToken}`;
```

**Risk:** URLs are logged by web servers, proxies, CDNs, and browsers. The `Referer` header leaks them to third-party scripts. Browser history stores them. A token in a URL has a much larger exposure surface than a token in an HTTP header or POST body. Severity: HIGH for session/auth tokens; MEDIUM for PII like patient IDs.

**Detection:**
```bash
grep -rn 'token=\${' src/
grep -rn 'redirect.*\?token' src/
grep -rn 'query.*token\|token.*query' src/
```

**Fix:** Put tokens in the POST body or an HTTP header, never in query parameters.

```ts
// Acceptable for magic links (token must be in the URL by nature)
// — but make it single-use, short-lived, and never log the full URL
const magicLink = `${BASE_URL}/auth/magic?t=${oneTimeToken}`;

// For API responses, put sensitive values in the body
res.json({ resetToken }); // not a redirect with token in URL
```

If magic links in URLs are unavoidable (email reset flows), ensure: single-use, 15-minute expiry, and suppress URL logging in the CDN/proxy for those paths.

---

## Cross-Site Scripting (XSS)

**Pattern:** User-controlled content inserted into HTML output without encoding.

```tsx
// UNSAFE — React: dangerouslySetInnerHTML with user content
<div dangerouslySetInnerHTML={{ __html: userBio }} />

// UNSAFE — direct DOM assignment
document.getElementById("message").innerHTML = req.query.msg;

// UNSAFE — server-side template without escaping
app.get("/search", (req, res) => {
  res.send(`<h1>Results for: ${req.query.q}</h1>`); // not escaped
});

// UNSAFE — href with user-controlled URL (javascript: protocol)
<a href={userSuppliedUrl}>Click here</a>
```

**Risk:** An attacker can inject JavaScript that runs in other users' browsers: steal session cookies (if not `HttpOnly`), exfiltrate data, perform actions as the victim, redirect to phishing pages. DOM-based XSS can bypass server-side defenses. Severity: HIGH for session hijacking potential; MEDIUM for reflected XSS with `HttpOnly` cookies (limited cookie theft, but still data exfiltration and action forgery).

**Detection:**
```bash
# React: dangerous HTML injection
grep -rn 'dangerouslySetInnerHTML' src/

# Direct DOM manipulation
grep -rn '\.innerHTML\s*=' src/
grep -rn 'document\.write(' src/

# Server-side string concatenation into HTML
grep -rn 'res\.send.*\${' src/
grep -rn 'res\.write.*\${' src/

# User-controlled href (javascript: protocol)
grep -rn 'href.*req\.\|href.*user\.' src/
```

**Fix:**
- In React, never use `dangerouslySetInnerHTML`. Render user content as text (React's default).
- For user-supplied URLs, validate the protocol is `http:` or `https:` only.
- For server-side rendering, use a template engine that auto-escapes (Nunjucks with autoescape, Handlebars) or explicitly escape: `htmlEncode(userInput)`.
- Add a `Content-Security-Policy` header that restricts inline scripts and trusted script sources.

---

## Missing Security Headers

**Pattern:** HTTP responses lack security headers that prevent entire classes of client-side attacks.

**Risk:** Each missing header leaves the door open to a specific attack class. Individually LOW severity; together they represent a meaningful defense-in-depth gap.

**Headers to verify:**

| Header | Missing risk | Recommended value |
|---|---|---|
| `Content-Security-Policy` | XSS, data injection | `default-src 'self'; script-src 'self'` (tighten per app) |
| `X-Frame-Options` | Clickjacking | `DENY` or `SAMEORIGIN` |
| `X-Content-Type-Options` | MIME sniffing attacks | `nosniff` |
| `Strict-Transport-Security` | Protocol downgrade / MITM | `max-age=31536000; includeSubDomains` |
| `Referrer-Policy` | Leaking URLs to third parties | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Unnecessary browser feature access | Restrict camera, mic, geolocation if unused |

**Detection:**
```bash
grep -rn 'X-Frame-Options\|Content-Security-Policy\|X-Content-Type\|Strict-Transport' src/
```

Check whether a middleware sets these globally, or whether they're set only on some responses.

**Fix:** Apply security headers globally in a middleware, not per-route.

```ts
// Hono example
app.use("*", secureHeaders({
  xFrameOptions: "DENY",
  xContentTypeOptions: "nosniff",
  strictTransportSecurity: "max-age=31536000; includeSubDomains",
  referrerPolicy: "strict-origin-when-cross-origin",
}));
```

For `Content-Security-Policy`, start with a report-only policy to identify violations before enforcing.

---

## Information Disclosure (Verbose Errors)

**Pattern:** Stack traces, internal paths, DB error details, or framework internals returned to clients.

```ts
// UNSAFE — raw error returned to client
app.use((err, req, res, next) => {
  res.status(500).json({ error: err.message, stack: err.stack });
});

// UNSAFE — DB error with query details leaked
try {
  await db.execute(query);
} catch (err) {
  res.status(500).json({ error: err }); // err may contain the SQL query
}
```

**Risk:** Stack traces reveal file paths, function names, library versions, and sometimes code snippets — all useful for an attacker planning a targeted exploit. DB errors can confirm injection payloads succeeded. Severity: MEDIUM (reduces attacker cost on other vulnerabilities).

**Detection:**
```bash
grep -rn 'err\.stack\|error\.stack' src/
grep -rn 'res\.json.*err\b\|res\.send.*err\b' src/
```

**Fix:** Return a generic error message to clients in production; log the full detail server-side.

```ts
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  logger.error("Unhandled error", { error: err.message, stack: err.stack });
  res.status(500).json({ error: "An unexpected error occurred" });
});
```

Use a separate error ID (e.g., a UUID) in the response and log to correlate without exposing internals:

```ts
const errorId = crypto.randomUUID();
logger.error("Unhandled error", { errorId, error: err.message, stack: err.stack });
res.status(500).json({ error: "An unexpected error occurred", errorId });
```

---

## Weak Cryptography and Insecure Randomness

**Pattern:** Using MD5/SHA-1 for password hashing, predictable values for tokens, or deprecated cipher modes.

```ts
// UNSAFE — MD5 for passwords (fast hash, not a password hash function)
const hash = crypto.createHash("md5").update(password).digest("hex");

// UNSAFE — SHA-256 alone for passwords (fast, brute-forceable)
const hash = crypto.createHash("sha256").update(password).digest("hex");

// UNSAFE — Math.random() for security-sensitive tokens (not cryptographically random)
const token = Math.random().toString(36).substring(2);

// UNSAFE — weak IV (fixed or zero IV in CBC mode)
const cipher = crypto.createCipheriv("aes-256-cbc", key, Buffer.alloc(16, 0));
```

**Risk:** Fast hash functions for passwords allow offline cracking with commodity hardware. `Math.random()` is seeded from a predictable state and can be predicted. Fixed IVs in block ciphers make encryption deterministic (same plaintext → same ciphertext), enabling statistical attacks. Severity: HIGH for password storage; MEDIUM for token generation; MEDIUM for encryption weaknesses.

**Detection:**
```bash
grep -rn "createHash('md5')\|createHash(\"md5\")" src/
grep -rn "createHash('sha1')\|createHash(\"sha1\")" src/
grep -rn "createHash('sha256')\|createHash(\"sha256\")" src/  # review context
grep -rn 'Math\.random()' src/
grep -rn 'createCipheriv' src/  # review IV handling
```

**Fix:**
- Passwords: use `bcrypt`, `argon2`, or `scrypt` — these are slow by design.
- Tokens: use `crypto.randomBytes(32).toString("hex")` — cryptographically random.
- Encryption: always generate a random IV per message and store it with the ciphertext.

```ts
import bcrypt from "bcrypt";
import { randomBytes } from "crypto";

// Password hashing
const hash = await bcrypt.hash(password, 12); // cost factor 12+

// Token generation
const token = randomBytes(32).toString("hex");

// AES-GCM with random nonce (preferred over CBC)
const iv = randomBytes(12);
const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
```
