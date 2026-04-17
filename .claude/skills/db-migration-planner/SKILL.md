---
name: db-migration-planner
description: >
  Plan a database migration between providers. Use this skill when the user has decided (or is close
  to deciding) to migrate databases and needs a concrete plan: schema compatibility, data migration
  steps, ORM changes, connection config updates, and rollback strategy.
  Trigger when the user says "plan the migration", "how do we move from D1 to Supabase", "migrate
  the database", "what do we need to do to switch from X to Y", or when a db-scalability-audit
  finding has recommended a migration and the user wants to act on it.
  Do NOT trigger for general scalability assessment — use db-scalability-audit for that.
---

## How to Run a Migration Plan

Your job is to produce a concrete, actionable migration plan for a specific source → target pair.
Before writing a single step, fully understand both sides: what the source schema looks like today,
and what the target provider requires.

---

## Step 0: Check for existing migration docs

Glob for `**/migration*.md`, `**/db-migration*.md`, `**/MIGRATION*.md` in the repo and `docs/`.
If a prior plan exists, read it — note what was decided, what was deferred, and what blockers were identified. Do not re-derive what's already been assessed.

---

## Step 1: Identify the migration pair

Confirm from the user or from context:
- **Source provider** (e.g., Cloudflare D1, Supabase, Neon)
- **Target provider** (e.g., Supabase Postgres, Neon, RDS)
- **Migration trigger** (limit hit, compliance requirement, cost, HIPAA BAA, etc.)

Then read the relevant playbook from [`references/migration-playbooks.md`](references/migration-playbooks.md).

---

## Step 2: Understand the current schema

Glob for schema files: `**/migrations/**`, `schema.sql`, `schema.prisma`, `drizzle.config.ts`.
For each table, note:
- Column types (especially DATE, BOOLEAN, JSON — these have cross-provider incompatibilities)
- FK constraints and cascade rules
- Indexes
- Any SQLite-specific syntax (functions, pragmas, type affinities)

---

## Step 3: Understand the query layer

Grep for the ORM in use (`drizzle`, `prisma`, `kysely`, `knex`, raw SQL strings).
Determine:
- Is the ORM dialect-specific or provider-agnostic?
- Are there raw SQL strings that use provider-specific functions?
- What driver/adapter changes are needed?

---

## Step 4: Identify blockers

A blocker is anything that will cause data loss, application errors, or a failed migration if not resolved first. Common blockers:

- SQLite type incompatibilities (see migration-playbooks.md for the full list)
- Provider-specific SQL functions in raw queries
- ORM adapter that doesn't support the target provider
- Auth/Storage services tied to the source provider (e.g., Supabase Auth + Supabase DB — can't move DB without also planning Auth)
- Missing BAA or compliance setup on the target (HIPAA cases)

List every blocker with a resolution and estimated effort.

---

## Step 5: Write the migration plan

Structure:

```markdown
# Database Migration Plan: <Source> → <Target>

**System:** <app name>
**Date:** <YYYY-MM-DD>
**Migration trigger:** <why this migration is happening>
**Planned approach:** <live cut-over / maintenance window / dual-write / blue-green>

## Blockers (resolve before starting)
| # | Issue | Resolution | Effort |
|---|---|---|---|

## Pre-migration steps
1. ...

## Migration steps
1. ...

## Post-migration validation
- [ ] Run smoke tests against target
- [ ] Verify row counts match between source and target
- [ ] Verify connection pooling is working correctly
- [ ] Check application error rates for 24h

## Rollback plan
<How to revert if the migration fails — what is the point of no return?>

## Sources
- <URL> — <what it was used for>
```

---

## Constraints

- Cite sources for any provider-specific claim (connection string format, driver package name, etc.)
- If a step requires human action that can't be scripted (e.g., clicking through a provider dashboard, signing a BAA), call it out explicitly as a manual step
- Always include a rollback plan — if there isn't a safe rollback point, flag it as a CRITICAL risk
- Do not include migration steps that assume zero downtime unless you've verified the approach supports it
