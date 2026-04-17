# Migration Playbooks

Common provider-to-provider migration paths, with known incompatibilities and step-by-step guidance.

---

## D1 (SQLite) → Supabase Postgres

**Difficulty:** Medium. SQLite and Postgres share SQL syntax but differ in types, functions, and behavior.

### Incompatibilities to resolve before migrating

| SQLite / D1 | Postgres equivalent | Notes |
|---|---|---|
| `INTEGER PRIMARY KEY` autoincrement | `SERIAL` or `BIGSERIAL` or `gen_random_uuid()` | D1 uses SQLite's implicit rowid for INTEGER PK |
| `TEXT` for everything | Proper types: `VARCHAR`, `TEXT`, `BOOLEAN`, `TIMESTAMP` | SQLite stores everything as text; Postgres is strictly typed |
| `BOOLEAN` stored as 0/1 | `BOOLEAN` (native) | ORM may handle automatically |
| `DATETIME` as TEXT | `TIMESTAMPTZ` | SQLite stores dates as ISO strings; Postgres has native timestamps |
| `json_extract(col, '$.field')` | `col->>'field'` (JSONB) | Different JSON extraction syntax |
| `PRAGMA foreign_keys = ON` | FKs enforced by default | Postgres enforces FKs natively; no PRAGMA needed |
| `AUTOINCREMENT` keyword | `GENERATED ALWAYS AS IDENTITY` | SQLite AUTOINCREMENT ≠ Postgres SERIAL semantics |
| No `RETURNING` clause (older D1) | `INSERT ... RETURNING id` | Postgres supports RETURNING; check if query layer uses it |
| `strftime('%Y-%m-%d', col)` | `TO_CHAR(col, 'YYYY-MM-DD')` | Date formatting functions differ |
| `LIKE` is case-insensitive | `ILIKE` for case-insensitive | Postgres `LIKE` is case-sensitive |

### Migration steps

1. **Export schema** from D1: `wrangler d1 export <DB_NAME> --output schema.sql --no-data`
2. **Export data**: `wrangler d1 export <DB_NAME> --output data.sql --no-schema`
3. **Adapt the schema** for Postgres:
   - Replace SQLite types with Postgres equivalents (see table above)
   - Replace `json_extract` with `->>`
   - Add `TIMESTAMPTZ` where dates were stored as TEXT
   - Review FK definitions — add `ON DELETE` rules explicitly
4. **Set up Supabase project** — enable HIPAA add-on if required (Team plan or higher)
5. **Apply schema** to Supabase via psql or Supabase dashboard SQL editor
6. **Transform and load data**: use a script to transform SQLite data dump to Postgres-compatible INSERT statements, handling type conversions
7. **Update connection config**:
   - Replace `wrangler.toml` D1 binding with Hyperdrive binding (or Supabase Pooler connection string)
   - Update env vars: remove `DB` binding, add `DATABASE_URL` or `HYPERDRIVE`
   - Update ORM config (Drizzle: switch from `drizzle-orm/d1` to `drizzle-orm/postgres-js` or `drizzle-orm/node-postgres`)
8. **Update ORM dialect**: Drizzle, Prisma, etc. need the Postgres driver — not the SQLite/D1 driver
9. **Audit raw SQL**: grep for SQLite-specific functions (see table above) and replace
10. **Test against Supabase** in staging before cut-over
11. **Cut-over**: update production secrets, deploy, validate

### Rollback plan
Keep D1 databases intact (do not delete) until the Supabase migration is confirmed stable. D1 exports can be re-imported if needed. Use feature flags or a maintenance window for the cut-over.

---

## D1 (SQLite) → Neon (Postgres)

Same incompatibilities as D1 → Supabase (both are Postgres). Key differences:

- Neon uses a standard Postgres connection string — no Hyperdrive needed for Workers, but Neon provides an HTTP query driver that works natively in edge runtimes
- Neon's HTTP driver (`@neondatabase/serverless`) works without TCP, making it suitable for Cloudflare Workers without Hyperdrive
- HIPAA BAA requires Neon Business plan ($700/mo)
- Neon's branching feature is useful for testing the migrated schema before cut-over

**Neon-specific connection for Workers:**
```ts
import { neon } from '@neondatabase/serverless';
const sql = neon(process.env.DATABASE_URL);
```

---

## SQLite → Postgres (general, any provider)

### Type mapping cheat sheet

```sql
-- SQLite → Postgres
INTEGER         → INTEGER or BIGINT
TEXT            → TEXT or VARCHAR(n)
REAL            → DOUBLE PRECISION or NUMERIC(p,s)
BLOB            → BYTEA
NUMERIC         → NUMERIC or DECIMAL
BOOLEAN (0/1)   → BOOLEAN (true/false)
DATETIME (text) → TIMESTAMPTZ
JSON (text)     → JSONB
```

### Function mapping cheat sheet

```sql
-- Date/time
strftime('%Y', col)          → EXTRACT(YEAR FROM col) or TO_CHAR(col, 'YYYY')
date('now')                  → NOW() or CURRENT_DATE
datetime('now')              → NOW()
julianday(col)               → (no direct equivalent — use EPOCH arithmetic)

-- String
||  (concat)                 → || or CONCAT()  (same in Postgres)
substr(col, start, len)      → SUBSTRING(col FROM start FOR len)
instr(col, substr)           → POSITION(substr IN col)
trim(col)                    → TRIM(col)  (same)

-- JSON
json_extract(col, '$.field') → col->>'field'  (JSONB text)
                             → col->'field'   (JSONB value)
json_each(col)               → jsonb_array_elements(col)

-- Conditional
ifnull(a, b)                 → COALESCE(a, b)
iif(cond, a, b)              → CASE WHEN cond THEN a ELSE b END
```

---

## Supabase → AWS RDS Postgres

**Difficulty:** Low (both are Postgres). Schema is compatible. Main work is infrastructure and connection config.

### Steps

1. Create RDS instance (or Aurora Serverless v2) in the appropriate VPC
2. Set up RDS Proxy for serverless connection pooling (required for Lambda/Workers)
3. `pg_dump` from Supabase: `pg_dump "postgresql://..." > dump.sql`
4. `psql` into RDS and restore: `psql "postgresql://..." < dump.sql`
5. Update connection strings in all environments
6. Configure security groups / VPC to allow ingress from the application runtime
7. Sign AWS BAA if HIPAA is required (AWS BAA covers RDS)
8. Disable Supabase project after confirming RDS is stable

### Key considerations
- Supabase Auth (GoTrue) is a separate service — if the app uses Supabase Auth, it cannot be migrated to RDS alone. Auth would need to be replaced (e.g., Cognito, Auth0, custom).
- Supabase Storage would also need to be replaced (e.g., S3).
- Row-Level Security (RLS) policies in Supabase are standard Postgres — they migrate cleanly.

---

## Assessing ORM Migration Readiness

When evaluating whether a migration is low-risk, check the ORM layer:

**Drizzle ORM:**
- D1 uses `drizzle-orm/d1` adapter → switch to `drizzle-orm/postgres-js` or `drizzle-orm/node-postgres`
- Schema definitions are largely reusable; column types may need updating (e.g., `text` → `timestamp`)
- Drizzle migrations are dialect-specific — the migration files must be regenerated for Postgres

**Prisma:**
- Switch `provider = "sqlite"` to `provider = "postgresql"` in `schema.prisma`
- Some field types need updating (DateTime, Boolean)
- Run `prisma migrate dev` against the new DB to regenerate migrations

**Raw SQL:**
- Highest migration risk — all SQLite-specific syntax must be found and replaced manually
- Grep for every raw query string; audit against the function/type mapping tables above
