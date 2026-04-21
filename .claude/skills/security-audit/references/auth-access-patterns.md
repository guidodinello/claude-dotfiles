# Auth & Access Control Patterns Reference

Catalog of authentication and authorization vulnerability patterns. These are the most common source of cross-user data exposure and privilege escalation.

---

## Missing Authentication on Routes

**Pattern:** An endpoint that operates on sensitive data is reachable without a valid session.

```ts
// UNSAFE — auth middleware applied at app level but this router bypasses it
const publicRouter = Router();
publicRouter.get("/admin/reports", reportHandler); // forgot to protect this route

// UNSAFE — guard applied inconsistently (some routes, not all)
router.get("/patients",    authMiddleware, listPatients);
router.get("/patients/:id",               getPatient);  // missing!
```

**Risk:** Unauthenticated access to any data the endpoint can reach. In healthcare, this is a direct PHI breach. Severity: CRITICAL for PHI-bearing endpoints; HIGH otherwise.

**Detection:**
1. List every route registration in the codebase.
2. For each route, check whether an auth middleware appears in its chain or is applied at the router level.
3. Pay extra attention to: routes added recently (git log), routes behind `/admin`, routes in sub-routers that may not inherit the parent's middleware.

```bash
# Find all route definitions
grep -rn 'router\.\(get\|post\|put\|patch\|delete\)' src/
grep -rn 'app\.\(get\|post\|put\|patch\|delete\)' src/

# Find auth middleware usage
grep -rn 'authMiddleware\|authenticate\|requireAuth\|verifyToken' src/
```

**Fix:** Apply auth middleware at the router level, not per-route. Per-route application makes it easy to forget one.

```ts
// Safe — middleware applied to the entire router
const protectedRouter = Router();
protectedRouter.use(authMiddleware);  // every route below is protected
protectedRouter.get("/patients", listPatients);
protectedRouter.get("/patients/:id", getPatient);
```

---

## Insecure Direct Object Reference (IDOR)

**Pattern:** A route trusts a user-supplied ID to scope a DB query, without verifying the authenticated user owns that record.

```ts
// UNSAFE — attacker changes :id in the URL to access any patient's data
router.get("/patients/:id/records", async (req, res) => {
  const records = await db.select().from(medicalRecords)
    .where(eq(medicalRecords.patientId, req.params.id)); // no ownership check
  res.json(records);
});

// UNSAFE — body ID trusted directly
router.post("/update-appointment", async (req, res) => {
  await db.update(appointments)
    .set({ notes: req.body.notes })
    .where(eq(appointments.id, req.body.appointmentId)); // could be someone else's
});
```

**Risk:** Any authenticated user can read or modify any other user's data. In healthcare this is cross-patient PHI exposure. Severity: CRITICAL for patient data; HIGH for other multi-user resources.

**Detection:**
1. Find every query that fetches by a primary or foreign key (`WHERE id = ?`, `.where(eq(...id, req.params.id))`).
2. For each, check whether the query also filters by the authenticated user's ID (`WHERE id = ? AND patient_id = ?`).
3. Alternatively, check whether there's a post-fetch ownership assertion before the response.

```bash
grep -rn 'req\.params\.id' src/
grep -rn 'req\.body\..*[Ii]d' src/
```

**Fix:** Always scope queries by the authenticated identity. Never trust the caller to supply the owner ID — derive it from the session.

```ts
// Safe — patient_id comes from the verified session, not the request
const patientId = req.session.patientId; // from JWT/session, not params
const records = await db.select().from(medicalRecords)
  .where(and(
    eq(medicalRecords.patientId, patientId),
    eq(medicalRecords.id, req.params.recordId) // scope to this patient
  ));
```

---

## Privilege Escalation (Vertical)

**Pattern:** A lower-privilege user can reach an endpoint or perform an action intended only for higher-privilege roles.

```ts
// UNSAFE — role check is present but only applied to some admin routes
router.delete("/users/:id", async (req, res) => {
  // No role check — any authenticated user can delete any user
  await db.delete(users).where(eq(users.id, req.params.id));
});

// UNSAFE — role checked in UI but not enforced server-side
// Frontend hides the button; backend has no guard
```

**Risk:** A regular user or patient can perform administrative actions (delete records, impersonate users, view all data, approve orders). Severity: HIGH.

**Detection:**
1. Find all admin/staff-only routes.
2. For each, verify a role/permission check exists in the handler or its middleware chain.
3. Check whether the role check happens server-side — client-side role checks (hidden UI elements) are not security controls.

```bash
grep -rn 'requireRole\|checkPermission\|isAdmin\|role.*admin' src/
```

**Fix:** Enforce roles server-side on every route that requires them. Client-side hiding is UX, not security.

```ts
function requireRole(role: string) {
  return (req, res, next) => {
    if (req.session.user?.role !== role) {
      return res.status(403).json({ error: "Forbidden" });
    }
    next();
  };
}

router.delete("/users/:id", requireRole("admin"), deleteUser);
```

---

## Cross-Site Request Forgery (CSRF)

**Pattern:** A state-changing endpoint (POST/PUT/PATCH/DELETE) does not verify that the request originated from the application's own frontend.

```ts
// UNSAFE — no CSRF token check on a state-changing action
router.post("/update-password", async (req, res) => {
  const { newPassword } = req.body;
  await updateUserPassword(req.session.userId, newPassword);
  res.json({ success: true });
});
```

**Risk:** An attacker tricks an authenticated user into visiting a malicious page that submits a form to the vulnerable endpoint. The browser sends the session cookie automatically, so the action executes as the victim. Severity: HIGH for account takeover actions (password change, email change, payment methods); MEDIUM for other mutations.

**Detection:**
Grep for `POST`, `PUT`, `PATCH`, `DELETE` route handlers. For each, check whether there is a CSRF token check, an `Origin`/`Referer` header check, or the endpoint uses a mechanism that inherently prevents CSRF (e.g., `Authorization` header with Bearer token — cookies-only auth is vulnerable).

**Note:** APIs that authenticate exclusively via `Authorization: Bearer` headers (not cookies) are not vulnerable to CSRF, because browsers do not automatically attach `Authorization` headers to cross-origin requests.

**Fix options:**
1. **Synchronizer token pattern:** Include a CSRF token in forms; verify it on the server.
2. **SameSite cookies:** Set session cookies to `SameSite=Strict` or `SameSite=Lax` — this prevents them from being sent on cross-site requests in modern browsers.
3. **Double-submit cookie:** Set a CSRF cookie and require the same value in a request header.
4. **Origin header check:** Reject requests whose `Origin` header doesn't match the expected domain (not reliable alone — some proxies strip it).

```ts
// SameSite cookie approach (simplest for most apps)
res.cookie("session", token, {
  httpOnly: true,
  secure: true,
  sameSite: "strict",
});
```

---

## JWT Weaknesses

**Pattern:** JWT tokens are issued or verified insecurely.

```ts
// UNSAFE — weak or hardcoded secret
const token = jwt.sign(payload, "secret");

// UNSAFE — algorithm confusion: accepts "none" algorithm
jwt.verify(token, secret); // without { algorithms: ["HS256"] } option

// UNSAFE — no expiry
jwt.sign(payload, secret); // missing expiresIn

// UNSAFE — secret in code, not env
const JWT_SECRET = "supersecret123";
```

**Risk:** A weak or hardcoded secret allows offline brute-force of tokens. Algorithm confusion (`alg: none`) allows forging arbitrary tokens with no signature. No expiry means stolen tokens are valid forever. Severity: CRITICAL for algorithm confusion; HIGH for weak/hardcoded secrets; MEDIUM for missing expiry.

**Detection:**
```bash
grep -rn 'jwt\.sign\|jwt\.verify' src/
grep -rn 'algorithms:' src/       # check if algorithm is pinned
grep -rn 'expiresIn' src/         # check if expiry is set
grep -rn 'JWT_SECRET\s*=' src/    # check for hardcoded value
```

**Fix:**
```ts
// Safe
jwt.sign(payload, process.env.JWT_SECRET!, {
  algorithm: "HS256",
  expiresIn: "1h",
});

jwt.verify(token, process.env.JWT_SECRET!, {
  algorithms: ["HS256"], // explicitly reject other algorithms including "none"
});
```

JWT secrets should be at least 256 bits (32 bytes) of random entropy. Never use a human-readable string.

---

## Broken Account Management

**Pattern:** Account takeover vectors in password reset, email change, or magic-link flows.

```ts
// UNSAFE — reset token is predictable (timestamp-based, sequential)
const resetToken = Date.now().toString();

// UNSAFE — token not invalidated after use (reusable reset link)
router.post("/reset-password", async (req, res) => {
  const { token, newPassword } = req.body;
  const user = await getUserByResetToken(token);
  await updatePassword(user.id, newPassword);
  // Missing: invalidate the token
});

// UNSAFE — no expiry check on reset token
const user = await db.select().from(users)
  .where(eq(users.resetToken, req.body.token)); // no WHERE expires_at > NOW()

// UNSAFE — email change without re-authentication or confirmation
router.post("/change-email", async (req, res) => {
  await db.update(users).set({ email: req.body.email })
    .where(eq(users.id, req.session.userId)); // no verification sent to new email
});
```

**Risk:** Predictable tokens allow account takeover by enumeration. Reusable tokens allow a previous reset link (e.g., from an email breach) to be replayed later. No expiry leaves accounts vulnerable indefinitely. Unverified email changes allow an attacker to redirect communication. Severity: HIGH for reusable/predictable tokens; MEDIUM for missing expiry.

**Detection:**
```bash
grep -rn 'resetToken\|reset_token\|magicLink\|magic_link' src/
```

For each generation site, check: is it cryptographically random? Does it expire? Is it invalidated on use?

**Fix:**
```ts
import { randomBytes } from "crypto";

// Cryptographically random token
const resetToken = randomBytes(32).toString("hex");

// Store with expiry
await db.update(users).set({
  resetToken,
  resetTokenExpiresAt: new Date(Date.now() + 15 * 60 * 1000), // 15 min
}).where(eq(users.id, userId));

// Validate and immediately invalidate
const user = await db.select().from(users)
  .where(and(
    eq(users.resetToken, token),
    gt(users.resetTokenExpiresAt, new Date()) // not expired
  )).get();

if (!user) return res.status(400).json({ error: "Invalid or expired token" });

await db.update(users).set({
  passwordHash: await hash(newPassword),
  resetToken: null,           // invalidate immediately
  resetTokenExpiresAt: null,
}).where(eq(users.id, user.id));
```
