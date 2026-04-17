# Database Anti-Patterns Reference

Catalog of schema and query anti-patterns that indicate scalability risk, grouped by category.

---

## Missing Indexes

**Pattern:** WHERE, JOIN ON, or ORDER BY on columns with no index.

```sql
-- No index on patient_id — full scan on every lookup
SELECT * FROM appointments WHERE patient_id = ?

-- No index on created_at — full scan to get recent records
SELECT * FROM events ORDER BY created_at DESC LIMIT 20
```

**Risk:** Every query does a full sequential scan (O(n)). As rows grow, query time grows linearly. At 100k+ rows this becomes visibly slow; at 1M+ rows it causes timeouts.

**Detection:** Cross-reference `WHERE`, `JOIN ON`, `ORDER BY` columns against `CREATE INDEX` statements in migrations.

**Fix:** Add a B-tree index on each frequently-queried column. For composite conditions (`WHERE a = ? AND b = ?`), add a composite index in the correct order.

---

## N+1 Query Pattern

**Pattern:** A query inside a loop, issuing one DB call per item.

```ts
// Fetches N patients, then issues N separate queries for appointments
const patients = await db.select().from(patients);
for (const patient of patients) {
  const appts = await db.select().from(appointments).where(eq(appointments.patientId, patient.id));
}
```

**Risk:** 1000 patients = 1001 round trips. At 10ms per query, that's 10 seconds per request. Kills performance and burns DB connections.

**Detection:** Grep for query calls (`.query`, `.select`, `.execute`, `db.`) inside `for`, `forEach`, `.map`, `.reduce`.

**Fix:** Use a single JOIN or a batched `WHERE id IN (...)` query, then group results in memory.

---

## Unbounded Collection Queries

**Pattern:** Querying a growing table with no LIMIT.

```ts
// Returns all rows — fine at 100 records, OOM at 1M
const allEvents = await db.select().from(analyticsEvents);
```

**Risk:** Memory exhaustion on the application server; query timeouts on the DB side. The query works in development (few rows) and silently becomes a production incident.

**Detection:** Grep for `.select()` or `SELECT *` from tables with unbounded growth patterns (events, logs, records, orders, audit trails) with no `.limit()` or `LIMIT` clause.

**Fix:** Add pagination (`LIMIT` + `OFFSET` or cursor-based), or use aggregates if the caller needs totals.

---

## JSON Column Abuse

**Pattern:** Filtering or sorting on values inside a JSON/JSONB column.

```sql
-- SQLite/D1: no efficient way to index inside JSON
SELECT * FROM forms WHERE json_extract(data, '$.status') = 'completed'

-- Postgres JSONB: possible to index but often forgotten
SELECT * FROM intake_submissions WHERE payload->>'email' = ?
```

**Risk:** Standard B-tree indexes can't be applied to JSON internals in SQLite. In Postgres, a GIN index helps for existence checks but not equality filters — a functional index is needed. Without the right index, every JSON filter is a full scan.

**Detection:** Grep for `json_extract`, `->`, `->>`, `.json`, `jsonb_`. Check whether those columns appear in WHERE clauses and whether corresponding functional or GIN indexes exist.

**Fix (Postgres):** Add a functional index: `CREATE INDEX ON table ((column->>'field'))`. For complex querying, extract the field to its own column.

**Fix (SQLite/D1):** Promote frequently-queried JSON fields to real columns. D1 has no JSON index support.

---

## Connection Exhaustion (Serverless)

**Pattern:** Direct DB connections from stateless/serverless runtimes without a connection pooler.

```ts
// Each Cloudflare Worker invocation opens a new Postgres connection
const client = new Client({ connectionString: process.env.DATABASE_URL });
await client.connect();
```

**Risk:** Each concurrent Worker invocation holds a DB connection for its lifetime. At 100 concurrent requests, that's 100 open connections. Postgres default max is 100 (Supabase free: 60). Beyond the limit, new connections are refused — 500 errors for all users.

**Detection:** Look for direct connection strings (port 5432) used from Cloudflare Workers, Lambda, or Vercel Edge. Look for absence of a pooler binding (`HYPERDRIVE`, PgBouncer, Supabase Pooler port 6543).

**Fix:** Use a connection pooler in Transaction mode:
- Cloudflare Workers: Hyperdrive
- General serverless: Supabase Pooler (port 6543, Transaction mode) or PgBouncer
- AWS Lambda: RDS Proxy

---

## SELECT *

**Pattern:** Selecting all columns when only a subset is needed.

```ts
const patient = await db.select().from(patients).where(eq(patients.id, id));
// Returns all 40 columns including large text fields, when only name + dob needed
```

**Risk:** Transfers more data than needed over the wire; prevents index-only scans (where Postgres can answer the query entirely from the index without touching the table). With large text/blob columns this materially increases query latency.

**Detection:** Grep for `.select()` with no column list, or `SELECT *` in raw SQL.

**Fix:** Specify the columns you need: `.select({ name: patients.name, dob: patients.dob })`.

---

## Missing Cascade / Orphaned Rows

**Pattern:** Child records referencing a deleted parent, with no foreign key or cascade rule.

```sql
-- No FK constraint — deleting a patient leaves orphaned appointments
DELETE FROM patients WHERE id = ?
-- appointments still have patient_id = <deleted id>
```

**Risk:** Orphaned rows accumulate silently, inflating table sizes and causing confusing query results (JOIN returns rows for non-existent parents).

**Detection:** Grep for `REFERENCES` in schema — are foreign keys defined? If not, check for delete operations on parent tables without corresponding child cleanup.

**Fix:** Add FK constraints with `ON DELETE CASCADE` (or `SET NULL` / `RESTRICT` depending on business logic). In D1, FK enforcement must be enabled explicitly: `PRAGMA foreign_keys = ON`.

---

## Table Bloat from Hard Deletes

**Pattern:** Hard-deleting rows from large, frequently-written Postgres tables.

```ts
await db.delete(appointments).where(eq(appointments.id, id));
```

**Risk:** Postgres uses MVCC — deleted rows aren't physically removed until `VACUUM` runs. On heavily-updated/deleted tables, dead tuples accumulate, inflating storage and degrading query performance. On hosted Postgres (Supabase, Neon), autovacuum runs automatically but can lag on high-write tables.

**Detection:** Look for hard-delete patterns (`DELETE FROM`) on tables that grow continuously or have high update rates.

**Fix:** Use soft deletes (`deleted_at` timestamp, filter with `WHERE deleted_at IS NULL`). If hard deletes are required, ensure autovacuum is not suppressed and monitor `pg_stat_user_tables.n_dead_tup`.

---

## Migrations Run Without Transactions

**Pattern:** DDL migrations executed without wrapping in a transaction.

```sql
-- No BEGIN/COMMIT — if this fails mid-way, schema is in an inconsistent state
ALTER TABLE patients ADD COLUMN insurance_id TEXT;
ALTER TABLE patients ADD COLUMN insurance_provider TEXT;
```

**Risk:** A partial failure leaves the schema in an inconsistent state that is hard to reason about and harder to roll back.

**Detection:** Look at migration files — do they wrap multi-statement migrations in `BEGIN; ... COMMIT;`?

**Note (D1):** D1 has limited transaction support in migrations. Postgres supports transactional DDL fully.

**Fix:** Wrap all multi-statement migrations in a transaction. Most migration frameworks (Drizzle, Flyway, Liquibase) do this automatically if configured correctly.

---

## No Query Timeout

**Pattern:** Long-running queries with no timeout set, blocking DB connections.

**Risk:** A slow query (e.g., a full scan triggered by an edge case) can hold a connection open indefinitely, starving other requests. One bad query can cascade into a full outage.

**Detection:** Grep for `statement_timeout`, `query_timeout`, `lock_timeout` in DB config or connection strings. Absence is the finding.

**Fix (Postgres):** Set `statement_timeout` at the connection level or role level:
```sql
SET statement_timeout = '5s';
-- Or in connection string: ?options=--statement_timeout%3D5000
```

**Fix (D1):** D1 enforces a 30-second query limit at the platform level. No manual configuration needed, but any query approaching that limit is a design problem.

---

## Missing Multi-Tenant Scoping

**Pattern:** Queries on tenant-bearing tables that don't filter by the tenant identifier.

```ts
// Missing org_id filter — returns all patients across every organization
const patients = await db.select().from(patients).where(eq(patients.status, 'active'));

// Correct — scoped to the authenticated tenant
const patients = await db.select().from(patients)
  .where(and(eq(patients.orgId, ctx.orgId), eq(patients.status, 'active')));
```

**Risk:** Two distinct risks in one pattern:
1. **Scalability** — the query scans every row in the table regardless of tenant. As tenant count and data volume grow, every such query degrades linearly. At 100 orgs with 10k patients each, an unscoped query reads 1M rows to return 10k.
2. **Data isolation** — patients, records, or analytics from one tenant are visible to another. In healthcare this is a HIPAA violation, not just a bug.

**Detection:**
1. Identify the tenant identifier column — common names: `org_id`, `organization_id`, `clinic_id`, `account_id`, `tenant_id`.
2. Find every table that has this column: grep for the column name in migration files.
3. For each such table, grep for queries against it and check that each one includes a `WHERE org_id = ?` (or ORM equivalent).
4. Pay extra attention to: list/search endpoints, analytics aggregates, background jobs, and any query that accepts a user-supplied ID.

```bash
# Find the tenant column
grep -r "org_id\|organization_id\|clinic_id" migrations/

# Find queries on a tenant-bearing table that may be missing the filter
grep -r "from(patients)\|from patients\|\.patients\." src/
# Then manually verify each result includes the tenant filter
```

**Fix:** Ensure every query on a tenant-bearing table filters by the authenticated tenant's ID — sourced from the session/JWT, never from user input.

```ts
// Pull tenant from auth context, not from request params
const orgId = ctx.auth.orgId; // from JWT, not req.params.orgId
const patients = await db.select().from(patients).where(eq(patients.orgId, orgId));
```

**Postgres hardening:** Row-Level Security (RLS) enforces tenant scoping at the database level, making it impossible to query across tenants even if application code forgets the filter. Supabase supports RLS natively. Consider it a defense-in-depth layer, not a substitute for application-level filtering.
