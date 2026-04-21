# Injection Patterns Reference

Catalog of injection vulnerability patterns, grouped by sink type. Each pattern includes the attacker's goal, how to detect it in code, and the concrete fix.

---

## SQL Injection

**Pattern:** User-controlled input concatenated or interpolated into a SQL query string.

```ts
// UNSAFE — attacker sends: ' OR '1'='1
const q = `SELECT * FROM patients WHERE name = '${req.query.name}'`;
await db.execute(q);

// UNSAFE — template literal that isn't the ORM's tagged template
const raw = "SELECT * FROM users WHERE id = " + req.params.id;
```

**Risk:** An attacker can bypass WHERE clauses (dump all rows), append UNION queries (exfiltrate other tables), or execute stacked queries (DROP TABLE, INSERT backdoor user). In healthcare, this is a direct PHI breach. Severity: CRITICAL if the endpoint is reachable.

**Detection:**
1. Grep for `SELECT`, `INSERT`, `UPDATE`, `DELETE` inside template literals or string concatenation.
2. Grep for `.execute(`, `.run(`, `.query(`, `.prepare(` receiving a variable rather than a literal.
3. Grep for `db.execute(\``, `db.query(\``, `sql\`${` — template literals fed directly into the query runner.
4. Cross-reference with all `req.params`, `req.query`, `req.body` ingestion points found in Step 1.

```bash
# Strings that interpolate variables directly into SQL
grep -rn 'SELECT.*\${' src/
grep -rn 'WHERE.*\+' src/
grep -rn '\.execute(`' src/
```

**Fix:** Use parameterized queries exclusively. The ORM's query builder is parameterized by design; raw SQL must use placeholders:

```ts
// Safe — ORM parameterized
await db.select().from(patients).where(eq(patients.name, req.query.name));

// Safe — raw SQL with placeholders (D1/SQLite style)
await db.prepare("SELECT * FROM patients WHERE name = ?").bind(req.query.name).first();

// Safe — raw SQL with placeholders (Postgres style)
await db.query("SELECT * FROM patients WHERE name = $1", [req.query.name]);
```

---

## Command Injection

**Pattern:** User-controlled input passed to a shell execution function without sanitization.

```ts
// UNSAFE — attacker sends: "; rm -rf /"
exec(`convert ${req.body.filename} output.png`);

// UNSAFE — shell: true with user input
spawn("sh", ["-c", `process ${userInput}`], { shell: true });
```

**Risk:** Full remote code execution on the application server. An attacker can read secrets from env, exfiltrate files, establish persistence, or pivot to internal systems. Severity: CRITICAL.

**Detection:**
Grep for `exec(`, `execSync(`, `spawn(`, `spawnSync(`, `execFile(`, `child_process`. For each call site, check whether any argument includes a variable derived from user input.

```bash
grep -rn 'exec\s*(' src/
grep -rn 'spawn\s*(' src/
grep -rn 'shell: true' src/
```

**Fix:** Avoid shell execution with user input entirely where possible. If unavoidable:
- Use `execFile` or `spawn` with an argument array (not `shell: true`) — arguments are passed directly, not through a shell interpreter.
- Validate the input against a strict allowlist before use.
- Never concatenate user input into a command string.

```ts
// Safe — argument array, no shell interpolation
spawn("convert", [req.body.filename, "output.png"], { shell: false });
```

---

## Path Traversal

**Pattern:** A file path is constructed from user-controlled input without validating it stays within the intended directory.

```ts
// UNSAFE — attacker sends: ../../etc/passwd
const filePath = path.join("/uploads", req.params.filename);
const content = fs.readFileSync(filePath);

// UNSAFE — same problem with query param
const template = path.resolve(__dirname, "templates", req.query.name);
```

**Risk:** An attacker can read arbitrary files on the server: source code, `.env`, private keys, `/etc/shadow`. If writes are involved, they can overwrite config or inject code. Severity: CRITICAL if the file read result is returned to the client.

**Detection:**
Grep for `readFile`, `createReadStream`, `path.join`, `path.resolve` where any segment comes from `req.params`, `req.query`, or `req.body`.

```bash
grep -rn 'readFile.*req\.' src/
grep -rn 'path\.join.*req\.' src/
grep -rn 'path\.resolve.*req\.' src/
```

**Fix:** After constructing the resolved path, assert it starts with the intended base directory before using it.

```ts
const base = path.resolve("/uploads");
const target = path.resolve(base, req.params.filename);

if (!target.startsWith(base + path.sep)) {
  throw new Error("Path traversal attempt blocked");
}

const content = fs.readFileSync(target);
```

Additionally, validate the filename against a strict allowlist (alphanumeric, hyphens, dots — no slashes) before path construction.

---

## Mass Assignment

**Pattern:** User-supplied object spread directly into a DB insert or update without filtering to an allowlist.

```ts
// UNSAFE — attacker can send { role: "admin", isActive: true } in the body
await db.update(users).set(req.body).where(eq(users.id, userId));

// UNSAFE — Prisma equivalent
await prisma.user.update({ where: { id }, data: req.body });
```

**Risk:** An attacker can elevate their role, activate disabled accounts, set internal flags, or overwrite fields they should never touch (e.g., `createdAt`, `stripeCustomerId`, `orgId`). Severity: HIGH for role-bearing fields; MEDIUM for non-sensitive fields.

**Detection:**
Grep for `.set(req.body)`, `.update({ data: req.body })`, `.create({ data: req.body })`, `...req.body` in DB calls.

```bash
grep -rn '\.set(req\.' src/
grep -rn 'data: req\.body' src/
grep -rn '\.\.\.req\.body' src/
```

**Fix:** Extract only the fields you intend to accept. Never pass the full request body to the database layer.

```ts
const { name, email, phone } = req.body;
await db.update(users).set({ name, email, phone }).where(eq(users.id, userId));
```

For complex input, use a validation library (zod, yup, Joi) to define the exact schema of accepted fields and strip everything else.

---

## Prototype Pollution

**Pattern:** User-supplied JSON with `__proto__` or `constructor` keys merged into an application object, polluting the global `Object.prototype`.

```ts
// UNSAFE — deep merge without key filtering
function merge(target: any, source: any) {
  for (const key of Object.keys(source)) {
    target[key] = source[key]; // key = "__proto__"
  }
}
merge({}, JSON.parse(req.body));

// UNSAFE — lodash < 4.17.12 _.merge was vulnerable
_.merge({}, userInput);
```

**Risk:** Attacker can add or override properties on `Object.prototype`, affecting every object in the process. This can bypass `if (obj.isAdmin)` checks, cause DoS by overriding `.toString`, or in some frameworks lead to RCE. Severity: HIGH for Node.js apps that use prototype-sensitive control flow.

**Detection:**
Grep for recursive merge/assign functions operating on user input. Check lodash/merge version. Look for `Object.assign` or spread with unchecked user input.

```bash
grep -rn '__proto__' src/
grep -rn 'constructor\.prototype' src/
```

**Fix:**
- Use `Object.create(null)` for dictionaries that should not inherit from `Object.prototype`.
- Sanitize parsed JSON keys before merging: reject or strip `__proto__`, `constructor`, `prototype`.
- Use `JSON.parse` with a reviver function that blocks these keys.
- Pin lodash to 4.17.21+ (patched).

```ts
function safeMerge(target: Record<string, unknown>, source: Record<string, unknown>) {
  for (const key of Object.keys(source)) {
    if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
    target[key] = source[key];
  }
}
```

---

## Server-Side Template Injection (SSTI)

**Pattern:** User-controlled input rendered inside a server-side template engine without sandboxing or escaping.

```ts
// UNSAFE — Handlebars/Nunjucks/EJS with user input in template string
const template = Handlebars.compile(req.body.template);
const output = template({ user });

// UNSAFE — EJS
res.render("page", { layout: req.query.layout });
```

**Risk:** In unsandboxed template engines, an attacker can execute arbitrary JavaScript on the server (RCE) or read application context (secrets, env vars). Severity: CRITICAL.

**Detection:**
Grep for `Handlebars.compile(`, `ejs.render(`, `nunjucks.renderString(`, `_.template(` where the first argument comes from user input.

**Fix:** Never pass user input as the template source. User input should only ever be template *data*, not the template itself. If user-defined templates are a feature requirement, use a sandboxed template engine (e.g., Nunjucks in sandbox mode) with a strict allowlist of permitted operations.
