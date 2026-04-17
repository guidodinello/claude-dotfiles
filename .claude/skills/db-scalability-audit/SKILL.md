---
name: db-scalability-audit
description: >
  Perform a Database Scalability & Architecture audit on a codebase. Use this skill whenever the
  user asks about database scalability, architecture review, migration planning, performance
  bottlenecks, or evaluating whether the current database setup will hold as usage grows.
  Also trigger when the user asks about switching providers (D1, Neon, Supabase, RDS, PlanetScale,
  etc.), storage limits, connection limits, or long-term DB strategy. Trigger phrases include:
  "will this scale", "DB migration", "database bottleneck", "should we move to Postgres",
  "scalability review", "D1 limits", "evaluate our DB setup".
---

## How to Run This Audit

Treat this as a technical due-diligence exercise, not a checklist. Your job is to map the current database landscape — provider, schema, query patterns, growth trajectory — and identify where the system will break or degrade before it actually does.

---

## Step 0: Check for existing audit docs

Glob for `**/database*.md`, `**/db-*.md`, `**/scalability*.md`, `**/architecture*.md`, `**/migration*.md` in the repo root and `docs/` directories. If prior reports exist:

- Read them to understand what was already assessed and decided
- Note any migration decisions that were made but not yet implemented
- Note any open items — carry those forward rather than re-deriving them
- If the prior doc conflicts with what you observe in code, flag the discrepancy

---

## Step 1: Orient yourself

Run these discovery steps before drawing any conclusions. Together they give you a full picture of the database surface.

**1. Identify the database provider(s)**
Look for `wrangler.toml` (D1, Hyperdrive bindings), `drizzle.config.ts`, `prisma/schema.prisma`, migration directories, and env vars (`DATABASE_URL`, `DB`, `HYPERDRIVE`, `SUPABASE_URL`, etc.). List every database in use — there may be more than one (e.g., one for analytics, one for core data).

**2. Find the schema**
Glob for `**/migrations/**`, `schema.sql`, `schema.prisma`, `drizzle.config.ts`. List every table, its approximate column count, and whether it has clearly unbounded growth (e.g., event/log tables, patient records, time-series data).

**3. Find the ORM / query layer**
Grep for `drizzle`, `prisma`, `kysely`, `knex`, `typeorm`, `sequelize`, raw SQL strings. Identify how queries are built and where they concentrate.

**4. Find high-traffic query paths**
Grep for the largest/most complex queries: JOINs, aggregates (`COUNT`, `SUM`, `GROUP BY`), full-table scans (no `WHERE` with an indexed column), and `SELECT *`. Find the endpoints that call them — these are the first to degrade under load.

**5. Find indexes**
In migration files, grep for `CREATE INDEX`, `index:`, `@@index`, `.index(`. List which tables have indexes and on which columns. Cross-reference against the high-traffic queries found in step 4 — missing indexes on JOIN columns or WHERE targets are a direct scalability risk.

**6. Find connection management**
Grep for connection pool config (`max`, `min`, `pool`, `connectionLimit`), connection string usage, and any connection-per-request patterns. Cloudflare Workers are stateless and create a new connection per invocation — if there's no pooler (Hyperdrive, pgBouncer, PgPool), this will exhaust DB connections rapidly at scale.

**7. Find unbounded queries**
Grep for queries with no `LIMIT` clause that return collections. A query that returns all rows of a growing table is a ticking time bomb.

**7a. Verify production call sites before assigning CRITICAL or HIGH severity**
For every dangerous query pattern you find (unbounded scan, missing index on a hot path, N+1, etc.), before assigning severity, verify the method or function that contains it is actually called in production code. Use grep to search for the method name across the entire codebase, explicitly excluding test files:
- Exclude: `**/__tests__/**`, `**/*.test.ts`, `**/*.spec.ts`, `**/*.test.tsx`
- If callers exist only in test files: the pattern is **dead code**. Downgrade to MEDIUM, note "no production callers — latent risk only", and recommend deletion rather than refactoring.
- If no callers exist at all: same treatment.
- If production callers exist: proceed with original severity assessment.

This one grep prevents false CRITICAL findings on dead code — a CRITICAL rating implies the failure mode is reachable today.

**8. Identify the storage and size situation**
Look for any documented DB sizes, provider dashboard notes, or comments about storage. Map against the known provider limits (see `references/provider-limits.md`). Flag tables that are clearly unbounded.

**9. Find multi-tenant scoping gaps**
Identify the tenant boundary — is it `org_id`, `organization_id`, `clinic_id`, `patient_id`, or similar? Grep for every query against tenant-bearing tables and check that each one filters by the tenant identifier. A query missing its tenant filter is both a full-table scan (scalability risk) and a data isolation failure (correctness risk). Pay particular attention to: list/search endpoints, analytics aggregates, and any query that accepts a user-supplied ID.

---

## Schema Anti-Pattern Reference

See [`references/anti-patterns.md`](references/anti-patterns.md) for the full catalog of schema and query anti-patterns by category:
- Missing indexes
- Unbounded growth tables
- N+1 query patterns
- Full-table scans
- Connection exhaustion
- JSON column abuse
- Cascade delete risks
- Multi-tenant scoping gaps

Key patterns to check inline:

**Missing indexes:** Find every `WHERE`, `JOIN ON`, and `ORDER BY` column in frequently-called queries. If those columns aren't indexed, every query does a full sequential scan.

**N+1 patterns:** Grep for query calls inside loops (`for`, `forEach`, `.map`). Each iteration issuing a separate query is a classic N+1 — 1000 records = 1000 round trips.

**Unbounded collections:** Grep for queries with no `LIMIT` returning from tables that grow continuously (events, logs, records, orders). These will eventually OOM or time out.

**JSON column abuse:** Grep for `jsonb`, `json`, `.json`. JSON columns can't be indexed with standard B-tree indexes, so filtering or sorting on nested JSON fields always causes a full scan.

**Hard-deletes on large tables:** Grep for `DELETE FROM` without soft-delete patterns. Hard-deleting from a large table causes table bloat and vacuuming pressure on Postgres.

**Multi-tenant scoping gaps:** Find the tenant identifier (`org_id`, `organization_id`, `clinic_id`, etc.). Grep for queries on tenant-bearing tables that don't filter by it. These cause full-table scans that grow with every tenant added — and silently return data across tenant boundaries.

---

## Provider Limits Reference

See [`references/provider-limits.md`](references/provider-limits.md) for a side-by-side table of storage caps, connection limits, row limits, and performance characteristics for:
- Cloudflare D1
- Supabase (free, pro, team, enterprise)
- Neon (free, launch, scale)
- PlanetScale
- AWS RDS / Aurora Serverless
- Turso

When auditing the current provider, always answer:
1. What is the current storage usage vs. the provider limit?
2. What is the projected growth rate — when will the limit be hit?
3. What happens at the limit — hard error, degraded performance, overage billing?
4. What connection limits apply, and how are connections managed under concurrent load?

---

## Migration Recommendation (audit scope only)

If the audit findings indicate a migration is warranted, include a brief recommendation in the findings — but do not plan the migration here. Migration planning is a separate activity handled by the `db-migration-planner` skill.

A migration recommendation finding should answer:
1. Is the current provider hitting a hard limit or a structural ceiling?
2. What is the recommended target provider and why?
3. What is the urgency — when does action need to happen?

Flag it as HIGH or MEDIUM severity depending on urgency. The `db-migration-planner` skill takes it from there.

---

## Reporting Format

### Document header

Start every report with:

```markdown
# Database Scalability & Architecture Audit

**System:** <app name>
**Date:** <YYYY-MM-DD>
**Auditor:** Claude Code (<model id>)
**Scope:** <what was covered — e.g. "Full schema review, query patterns, provider limits, migration readiness for D1 → Supabase">
```

### Overall Assessment

Follow the header with a 2-4 sentence executive summary: current state, primary risk, and the single most important action. This is what a non-technical stakeholder reads.

### Database Surface Map

Before any findings, include:
1. A **Databases in Use** table: name/binding, provider, current size (if known), primary purpose
2. A **Tables at Risk** table: table name, growth pattern (bounded/unbounded), indexed (YES/NO), notes

### Findings

Group findings under severity headings. Use sequential IDs so the remediation table can reference them.

```markdown
### CRITICAL
**C-1: <short title>**
- Location: `path/to/file.ts:line` or `table_name`
- Finding: What you observed
- Risk: The specific scalability failure this causes and at what scale (e.g., "connection exhaustion above ~50 concurrent requests")
- Recommendation: Concrete fix

### HIGH
**H-1: <short title>**
...

### MEDIUM
**M-1: <short title>**
...

### LOW
**L-1: <short title>**
...

### INFO
**I-1: <short title>**
...
```

**Severity levels:**
- **CRITICAL** — Will cause an outage, data loss, or cross-tenant data exposure at current/near-term scale. No mitigation in place. **Cross-tenant data exposure is always CRITICAL regardless of performance impact** — if a query returns data across org/tenant boundaries, it is CRITICAL even if the query itself is fast. **Dead code cannot be CRITICAL** — if the dangerous pattern exists in a method with no production callers (verified via grep excluding test files), cap severity at MEDIUM.
- **HIGH** — Significant performance degradation or data integrity risk under moderate load. Needs fixing before next growth phase.
- **MEDIUM** — Won't cause immediate failure but will compound over time or require emergency work later.
- **LOW** — Best-practice gaps that are low-urgency but worth tracking.
- **INFO** — Two uses: (1) observations that can't be fully assessed from code alone (provider pricing, ops config); (2) **positive controls** — things working well. Prefix positive controls with "Positive control —".

Do not put "What's Working Well" in a separate section. Positive controls belong in `### INFO` as `I-*` findings.

### Prioritized Remediation

Use consistent effort estimates across the table so items are comparable:

| Label | Meaning |
|---|---|
| Tiny | < 30 min — a one-liner, a config change, an env var |
| Small | 30 min – 2 hr — a single function, a migration with no data transform |
| Medium | 2–8 hr — a migration with data transform, ORM changes, or cross-service coordination |
| Large | 1–3 days — architectural change, RLS policy rollout, requires end-to-end testing |
| XL | > 3 days — multi-sprint work, requires planning and staged rollout |

```markdown
## Prioritized Remediation

### Address immediately
| # | Finding | Effort |
|---|---|---|

### Address within 30 days
| # | Finding | Effort |
|---|---|---|

### Address within 90 days
| # | Finding | Effort |
|---|---|---|
```

### Sources Cited

End with a **Sources** section listing every external URL referenced in the report — provider docs, benchmark posts, official migration guides. This is required whenever a finding cites a provider limit, pricing tier, or external claim.

```markdown
## Sources

- [Supabase connection limits](https://supabase.com/docs/guides/platform/limits) — connection pool limits per plan tier
- [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/) — storage and query constraints
```

No citation, no claim. If a limit or constraint can't be sourced, flag it as INFO with a note to verify manually.

### Key Files Reference

End with a two-column table mapping file paths to their database-relevant purpose.
