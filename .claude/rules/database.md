---
paths:
  - "**/alembic/**"
  - "**/migrations/**"
  - "**/*.sql"
  - "**/models/**"
---

# Database — Agent Design Guidelines

Guidelines for PostgreSQL schema design, constraint discipline, indexing, and migration
hygiene. These rules are expressed at the SQL/schema level and apply regardless of the
ORM or migration tool in use.

---

## Philosophy

- **The schema is the source of truth** — the application is derived from it, not the
  other way around. If a constraint belongs in the schema (FK, unique, check), put it
  there; don't rely on application-layer validation as the only guard.
- **Explicit over implicit** — name every constraint and index. Auto-generated names are
  unpredictable across databases and make migrations harder to read and reverse.
- **Write once, migrate forward** — never hand-edit a migration after it has been applied
  to any shared environment (staging, production). Always write a new migration.
- **Fail loud on bad data** — prefer `NOT NULL`, `CHECK`, and FK constraints over
  nullable columns that silently allow corrupt state.

---

## Naming conventions

| Object | Pattern | Example |
| -------- | --------- | --------- |
| Table | `snake_case`, plural | `users`, `onboarding_sessions` |
| Column | `snake_case` | `email_verified_at`, `user_id` |
| Primary key | `id` | — |
| Foreign key column | `{referenced_table_singular}_id` | `user_id`, `item_id` |
| FK constraint | `{table}_{col}_fkey` | `interactions_user_id_fkey` |
| Unique constraint | `uq_{table}_{cols}` | `uq_credentials_type_identifier` |
| Check constraint | `ck_{table}_{condition}` | `ck_items_price_positive` |
| Index (non-unique) | `ix_{table}_{cols}` | `ix_price_snapshots_item_id_recorded_at` |
| Unique index | `uix_{table}_{cols}` | `uix_items_external_id_source_id` |

Always supply explicit constraint and index names — never let the tool auto-generate them.

---

## Column design

### Prefer `NOT NULL` by default

Only allow `NULL` when absence is meaningful — a nullable FK, an optional field, or a
timestamp-as-state column like `email_verified_at`. A column that should always have a
value must be `NOT NULL`. Add a `DEFAULT` if the column is added to an existing table
(or see "Zero-downtime migrations" for the nullable-first approach on large tables).

### Always store timestamps with timezone

Never use a timezone-naive timestamp type (`TIMESTAMP` without `WITH TIME ZONE`). All
timestamps are stored as `TIMESTAMPTZ` and written in UTC by the application.
Timezone-naive timestamps are ambiguous under DST and break multi-region deployments.

```sql
-- Good
created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

-- Avoid
created_at TIMESTAMP NOT NULL DEFAULT NOW()
```

### Nullable timestamp over boolean flag

For any **permanent, one-way state transition**, use a nullable `TIMESTAMPTZ` column
instead of a `BOOLEAN`. `NULL` means "not yet happened"; a non-`NULL` value means
"happened at this instant". The boolean semantics are preserved and the timestamp is
gained at no extra cost.

```sql
-- Good — encodes both state and time
email_verified_at TIMESTAMPTZ NULL

-- Avoid — discards when it happened
email_verified BOOLEAN NOT NULL DEFAULT FALSE
```

Apply this pattern when all three hold: the transition is **permanent**, **one-way**, and
the time is at least plausibly useful (support, analytics, compliance). Reversible states
(feature flags, pause toggles) keep a boolean — the timestamp adds nothing there.

**Migration rule:** always backfill in the same migration. A query gating on `IS NULL`
will silently match all existing rows if they are not backfilled on deploy:

```sql
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ NULL;
UPDATE users SET email_verified_at = NOW();  -- grandfather existing rows
```

### Soft deletes

Use `deleted_at TIMESTAMPTZ NULL` to implement soft deletion. `NULL` = active;
non-`NULL` = deleted at that instant.

```sql
deleted_at TIMESTAMPTZ NULL
```

**Partial indexes are required alongside soft deletes.** Most queries should only touch
active rows, and unique constraints must exclude deleted rows. Add a partial index for
every access pattern that filters on the active set:

```sql
-- Replace a plain index with a partial one
CREATE INDEX ix_posts_author_id ON posts(author_id) WHERE deleted_at IS NULL;

-- Unique constraint that allows re-use of an email after soft deletion
CREATE UNIQUE INDEX uix_users_email_active ON users(email) WHERE deleted_at IS NULL;
```

Without the partial unique index, a soft-deleted row blocks re-registration with the
same email.

### Enum-like columns: TEXT with a CHECK constraint

Do not use PostgreSQL `ENUM` types for application-defined enumerations. `ALTER TYPE`
to add or remove a member takes an `ACCESS EXCLUSIVE` lock and requires a full table
rewrite in older PostgreSQL versions. Instead, store values as `TEXT` and enforce the
allowed set with a `CHECK` constraint at the schema level:

```sql
-- Good — plain text, enforced by the schema
event_type TEXT NOT NULL,
CONSTRAINT ck_events_event_type CHECK (event_type IN ('purchase', 'view', 'click'))

-- Avoid — requires ALTER TYPE to add/remove values; DDL-locks the table
event_type eventtype NOT NULL  -- PostgreSQL ENUM type
```

Adding a new value requires only an `ALTER TABLE ... DROP CONSTRAINT ... ADD CONSTRAINT`
— no lock escalation. If the ORM validates the set as well, that's defence-in-depth, not
a substitute for the `CHECK` constraint.

### CHECK constraints

Use `CHECK` constraints for any invariant that can be expressed as a boolean expression
over one or more columns in the same row:

```sql
-- positive price
CONSTRAINT ck_products_price_positive CHECK (price > 0)

-- end must be after start
CONSTRAINT ck_bookings_dates CHECK (ends_at > starts_at)

-- mutually exclusive nullable FKs
CONSTRAINT ck_notifications_target CHECK (
    (user_id IS NOT NULL)::int + (team_id IS NOT NULL)::int = 1
)
```

Prefer a `CHECK` constraint over equivalent application code whenever the rule must hold
for all writers (migrations, seed scripts, direct SQL access).

### Primary key type

Use `BIGSERIAL` (or `BIGINT GENERATED ALWAYS AS IDENTITY`) as the default primary key
type. Plain `INTEGER` overflows at ~2.1 billion rows, which is reachable on
high-throughput tables.

```sql
-- Preferred
id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY

-- Acceptable for small, stable tables
id SERIAL PRIMARY KEY

-- Avoid for new tables
id INTEGER PRIMARY KEY
```

UUID primary keys are appropriate for distributed systems or when rows are created
client-side before they are persisted (offline-first, multi-tenant sharding). They carry
a write-amplification cost from random index insertions; benchmark before defaulting to
them.

### NULL semantics in unique constraints

PostgreSQL treats `NULL` as distinct from every other value, including other `NULL`s. A
standard unique index allows multiple rows where the indexed column is `NULL`. This is
often the desired behaviour for optional-unique columns (e.g. `external_id`), but
confirm it is intentional:

```sql
-- Multiple NULLs are allowed — correct for an optional external reference
CREATE UNIQUE INDEX uix_products_external_id ON products(external_id);

-- If only one NULL should be allowed, enforce with a CHECK constraint instead
```

---

## Foreign keys and cascade behavior

Declare an explicit `ON DELETE` action on every FK constraint. Defaulting to the
implicit `NO ACTION` (which raises an error on parent deletion) is rarely the intended
behavior and is easy to miss in code review.

Choose the action based on the deletion policy of the parent table:

| Parent deletion policy | Child action |
| --- | --- |
| Hard-deleted; child rows are meaningless without parent | `ON DELETE CASCADE` |
| Hard-deleted; child rows must be retained (audit log, historical record) | `ON DELETE SET NULL` with nullable FK |
| Never deleted | `ON DELETE RESTRICT` (or omit — same effect) |

Document the deletion policy for each root entity in the project and derive cascade rules
from it consistently.

```sql
-- Child rows are meaningless without the parent
user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE

-- Child rows must survive parent deletion (nullable FK)
deleted_by_user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL
```

### Adding CASCADE to an existing FK constraint

Drop and recreate the constraint — `ALTER TABLE` cannot modify an existing FK's action:

```sql
ALTER TABLE interactions DROP CONSTRAINT interactions_user_id_fkey;
ALTER TABLE interactions ADD CONSTRAINT interactions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
```

---

## Indexing

### Index every FK column

PostgreSQL does not automatically index FK columns. An un-indexed FK causes a sequential
scan on the child table for every JOIN or cascade operation on that column. Create the
index in the same migration that adds the FK:

```sql
CREATE INDEX ix_interactions_user_id ON interactions(user_id);
```

### Composite index column order

Put equality-filter columns first, range or sort columns last. This matches B-tree
traversal order:

```sql
-- Good — filters by item_id (equality) then sorts by recorded_at (range)
CREATE INDEX ix_price_snapshots_item_id_recorded_at
    ON price_snapshots(item_id, recorded_at);
```

### Partial indexes

When a query always filters on a condition, push that condition into the index definition
to reduce index size and improve selectivity:

```sql
-- Index only active (non-deleted) rows
CREATE INDEX ix_orders_user_id ON orders(user_id) WHERE deleted_at IS NULL;

-- Index only rows in a specific state
CREATE INDEX ix_jobs_created_at ON jobs(created_at) WHERE status = 'pending';
```

A partial index is usually paired with soft deletes (see above) and with sparse boolean
or status columns where one value dominates.

### Don't over-index

Each index adds write overhead and storage cost. Add an index only when:

- The column is a FK (always)
- A query filter or sort on the column exists in the codebase
- `EXPLAIN ANALYZE` confirms a sequential scan on a large table

Don't add indexes speculatively. Unused indexes slow every `INSERT`/`UPDATE` for zero
query benefit.

### Approximate nearest-neighbour index for vector columns (pgvector)

Requires the `pgvector` extension. Exact `<=>` similarity scans are O(n); for tables
beyond a few thousand rows, create an IVFFlat (fast to build) or HNSW (faster queries)
index:

```sql
CREATE INDEX ON items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- or
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);
```

Set `lists ≈ sqrt(row_count)` for IVFFlat. Re-index when the table grows by an order of
magnitude.

---

## Upsert and deduplication

Use `INSERT ... ON CONFLICT` for idempotent writes and deduplication. The target of `ON
CONFLICT` must be a column or columns covered by a unique constraint or unique index:

```sql
-- Idempotent insert — ignore duplicates
INSERT INTO event_log (idempotency_key, payload)
VALUES ('abc123', '{}')
ON CONFLICT (idempotency_key) DO NOTHING;

-- Upsert — overwrite on conflict
INSERT INTO product_prices (product_id, currency, amount)
VALUES (1, 'USD', 9.99)
ON CONFLICT (product_id, currency)
DO UPDATE SET amount = EXCLUDED.amount, updated_at = NOW();
```

`EXCLUDED` refers to the row that was rejected. Use `DO NOTHING` for at-least-once
ingestion; use `DO UPDATE` when the latest value should win.

---

## Pagination

**Prefer keyset (cursor) pagination over offset pagination for large or frequently
updated datasets.**

Offset pagination (`LIMIT n OFFSET m`) scans and discards `m` rows on every page. At
large offsets this becomes expensive and produces inconsistent results when rows are
inserted or deleted between pages.

```sql
-- Offset pagination — avoid on large tables
SELECT * FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 1000;

-- Keyset pagination — O(log n) via index seek
SELECT * FROM posts
WHERE created_at < :last_seen_cursor
ORDER BY created_at DESC
LIMIT 20;
```

For keyset pagination to work, the sort column(s) must be indexed and the cursor value
must be stable across requests. Composite cursors (`(created_at, id)`) handle ties.

Offset pagination is acceptable for small, rarely-changing tables where total-row-count
display is required (traditional page numbers).

---

## Migration discipline

### One logical change per migration

Each migration file should represent one unit of related schema work: creating a table
with its initial indexes counts as one unit; adding an unrelated column to a different
table is a second migration. Split unrelated changes so they can be reviewed, rolled
back, and cherry-picked independently.

### Always write a `downgrade`

Every migration must have a `downgrade` path. A `downgrade` that is left empty is not
acceptable for structural changes (adding/dropping tables, columns, constraints, indexes).

```sql
-- upgrade
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ NULL;
UPDATE users SET email_verified_at = NOW();

-- downgrade
ALTER TABLE users DROP COLUMN email_verified_at;
```

For irreversible data operations (e.g. backfilling a column that is then dropped
elsewhere), document the downgrade explicitly as a no-op and explain why rollback
requires a restore:

```python
def downgrade():
    # Irreversible: source column was dropped in migration 0042.
    # Rolling back requires restoring from backup.
    pass
```

### Review auto-generated migrations before committing

ORM autogenerate is a starting point, not a final answer. Always check:

- FK constraints have the correct `ON DELETE` action (autogenerate commonly omits it)
- Index and constraint names are explicit, not auto-generated
- A backfill `UPDATE` is present if a new `NOT NULL` column is added to a populated table
- `server_default` values are correct and will not break existing rows

### Zero-downtime migrations for large tables

A migration that adds a `NOT NULL` column without a default, or that rebuilds an index,
acquires a full table lock and will block reads and writes for the duration. For tables
with significant traffic:

1. **Add the column as nullable first**, backfill in batches, then add the `NOT NULL`
   constraint once all rows are populated.
2. **Build indexes `CONCURRENTLY`** to avoid the lock:

   ```sql
   CREATE INDEX CONCURRENTLY ix_interactions_user_id ON interactions(user_id);
   ```

Note: `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block. If your
migration tool wraps each migration in a transaction, disable that wrapping for this
migration.

---

## Quick reference checklist

### Adding a new column

- [ ] Timestamp columns use `TIMESTAMPTZ`, never `TIMESTAMP`
- [ ] Boolean-like columns: should this be a nullable `TIMESTAMPTZ` instead? (see above)
- [ ] `NOT NULL` unless absence is semantically meaningful
- [ ] Backfill included in the migration if existing rows need a value
- [ ] `DEFAULT` provided if the column is `NOT NULL` on an existing table (or use nullable-first approach)
- [ ] Enum-like columns: `TEXT` + `CHECK` constraint, not PostgreSQL `ENUM`
- [ ] Soft-delete column: paired with a partial index for every relevant unique constraint and access pattern

### Adding a new table

- [ ] Table name is plural `snake_case`
- [ ] Primary key is `BIGINT GENERATED ALWAYS AS IDENTITY` (or `BIGSERIAL`); avoid plain `INTEGER`
- [ ] Every FK column has an explicit `ON DELETE` action matching the parent's deletion policy
- [ ] Every FK column has a corresponding index (`ix_{table}_{col}`)
- [ ] All constraint and index names are explicit
- [ ] Soft-deleted tables have a `deleted_at TIMESTAMPTZ NULL` column and partial indexes

### Adding a new migration

- [ ] Single logical unit of change per file
- [ ] Both `upgrade` and `downgrade` are complete (or downgrade documents why it is a no-op)
- [ ] Auto-generated output reviewed for missing `ON DELETE`, constraint names, backfills
- [ ] Tested: upgrade then downgrade both succeed cleanly against a dev database
- [ ] Large-table changes use `CONCURRENTLY` or a staged nullable-then-constrain approach
- [ ] `CONCURRENTLY` index creation runs outside a transaction block if required by the migration tool
