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
  to any environment. Always write a new migration.
- **Fail loud on bad data** — prefer `NOT NULL`, `CHECK`, and FK constraints over
  nullable columns that silently allow corrupt state.

---

## Naming conventions

| Object | Pattern | Example |
|--------|---------|---------|
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

**Migration rule:** always backfill in the same migration. A nightly job gating on
`IS NULL` will silently delete all existing rows if they are not backfilled on deploy:

```sql
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ NULL;
UPDATE users SET email_verified_at = NOW();  -- grandfather existing rows
```

### Store enum values as text, enforce at the application layer

Do not use PostgreSQL `ENUM` types for application-defined enumerations. Store values as
`VARCHAR` / `TEXT` and enforce the valid-value constraint at the ORM or application
layer. This avoids the DDL overhead and migration friction of `ALTER TYPE` when members
change.

```sql
-- Good — plain text column; constraint enforced by the ORM
event_type VARCHAR NOT NULL

-- Avoid — requires ALTER TYPE to add/remove values, DDL-locks the table
event_type eventtype NOT NULL  -- PostgreSQL ENUM type
```

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

### Prefer `NOT NULL` by default

Only allow `NULL` when absence is meaningful — a nullable FK, an optional field, or a
timestamp-as-state column like `email_verified_at`. A column that should always have a
value must be `NOT NULL`. Add a `DEFAULT` if the column is added to an existing table.

---

## Foreign keys and cascade deletes

### Declare `ON DELETE CASCADE` for FK children of hard-deletable parents

When a parent table supports hard deletes (currently only `users`), declare
`ON DELETE CASCADE` on every FK column that references it. This ensures child rows are
automatically removed when the parent is deleted, with no manual enumeration in
application code.

```sql
-- Good
user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE

-- Avoid — requires manual DELETE of every child table before deleting the parent;
-- breaks silently when a new child table is added
user_id INTEGER NOT NULL REFERENCES users(id)
```

Without `CASCADE`, every deletion path must enumerate all child tables. A new table
added later that doesn't get added to the deletion path will cause an FK violation at
runtime — with no compile-time or lint-time warning.

### When NOT to use CASCADE

- **`items` FK children** — items are never hard-deleted (invariant); the question of
  cascade does not arise. Omit `ON DELETE` entirely.
- **Retained records** — if child rows must outlive the parent (e.g. an audit log kept
  independently of the user), use `ON DELETE SET NULL` with a nullable FK instead.

### Adding CASCADE to an existing FK constraint

Drop and recreate the constraint:

```sql
ALTER TABLE interactions DROP CONSTRAINT interactions_user_id_fkey;
ALTER TABLE interactions ADD CONSTRAINT interactions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
```

---

## Indexing

### Index every FK column

PostgreSQL does not automatically index FK columns. An un-indexed FK causes a sequential
scan on the child table for every JOIN, cascade operation, or filter on that column.

```sql
CREATE INDEX ix_interactions_user_id ON interactions(user_id);
```

Create this index in the same migration that adds the FK.

### Composite index column order

Put equality-filter columns first, range or sort columns last. This matches B-tree
traversal order:

```sql
-- Good — filters by item_id (equality) then sorts by recorded_at (range)
CREATE INDEX ix_price_snapshots_item_id_recorded_at
    ON price_snapshots(item_id, recorded_at);
```

### Approximate nearest-neighbour index for vector columns (IVFFlat / HNSW)

Exact `<=>` similarity scans are O(n). For tables beyond a few thousand rows, create an
IVFFlat (fast to build) or HNSW (faster queries) index:

```sql
CREATE INDEX ON items USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- or
CREATE INDEX ON items USING hnsw (embedding vector_cosine_ops);
```

Set `lists ≈ sqrt(row_count)` for IVFFlat. Re-index when the table grows by an order of
magnitude. The `vector` extension must exist before creating either index type.

### Don't over-index

Each index adds write overhead and storage cost. Add an index only when:
- The column is a FK (always)
- A query filter or sort on the column exists in the codebase
- `EXPLAIN ANALYZE` confirms a sequential scan on a large table

Don't add indexes speculatively. Unused indexes slow every `INSERT` / `UPDATE` for zero
query benefit.

---

## Migration discipline

### One logical change per migration

Each migration file should do exactly one thing: add a table, add a column, add an
index. Split unrelated changes into separate migrations so they can be reviewed, rolled
back, and cherry-picked independently.

### Always write a `downgrade`

Every migration must be fully reversible. A `downgrade` that raises an error or is left
empty is not acceptable — it means the migration can never be safely rolled back in
production.

```sql
-- upgrade
ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMPTZ NULL;
UPDATE users SET email_verified_at = NOW();

-- downgrade
ALTER TABLE users DROP COLUMN email_verified_at;
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

1. **Add the column as nullable first**, then backfill in batches, then add the
   `NOT NULL` constraint once all rows are populated.
2. **Build indexes `CONCURRENTLY`** to avoid the lock:
   ```sql
   CREATE INDEX CONCURRENTLY ix_interactions_user_id ON interactions(user_id);
   ```

---

## Quick reference checklist

### Adding a new column

- [ ] Timestamp columns use `TIMESTAMPTZ`, never `TIMESTAMP`
- [ ] Boolean-like columns: should this be a nullable `TIMESTAMPTZ` instead? (see "Nullable timestamp over boolean flag" above)
- [ ] `NOT NULL` unless absence is semantically meaningful
- [ ] Backfill included in the migration if existing rows need a value
- [ ] `DEFAULT` provided if the column is `NOT NULL` on an existing table

### Adding a new table

- [ ] Table name is plural `snake_case`
- [ ] Primary key is `id` (autoincrement integer)
- [ ] FK columns referencing hard-deletable parents include `ON DELETE CASCADE`
- [ ] FK columns referencing `items` omit `ON DELETE` (items are never deleted)
- [ ] Every FK column has a corresponding index (`ix_{table}_{col}`)
- [ ] Enum-like columns use `VARCHAR` / `TEXT`, not PostgreSQL `ENUM`
- [ ] All constraint and index names are explicit

### Adding a new migration

- [ ] Single logical change per file
- [ ] Both `upgrade` and `downgrade` are complete and correct
- [ ] Auto-generated output reviewed for missing `ON DELETE`, constraint names, backfills
- [ ] Tested: upgrade then downgrade both succeed cleanly against a dev database
- [ ] Large-table changes use `CONCURRENTLY` or a staged nullable-then-constrain approach
