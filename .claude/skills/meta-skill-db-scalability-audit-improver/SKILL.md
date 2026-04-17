---
name: meta-skill-db-scalability-audit-improver
description: >
  Improve and update the db-scalability-audit skill by fetching current provider documentation and
  verifying that limits, pricing, and connection constraints in provider-limits.md are accurate.
  Use this skill when the user wants to refresh the DB audit references, check if provider limits
  have changed, or keep the audit skill current with the latest provider offerings.
  Trigger phrases: "update the DB audit skill", "refresh provider limits", "check if D1 limits changed",
  "run the DB skill updater".
compatibility:
  tools:
    - WebFetch
  allowed_domains:
    - developers.cloudflare.com
    - supabase.com
    - neon.tech
    - planetscale.com
    - aws.amazon.com
    - docs.aws.amazon.com
    - turso.tech
---

## What this skill does

Fetches official provider documentation and verifies that `provider-limits.md` reflects current limits, pricing tiers, and connection constraints. Updates the file with accurate, sourced content and writes an update log.

Only modifies files inside `~/.claude/skills/db-scalability-audit/references/`. Never touches `SKILL.md`.

---

## Step 1 — Read current state

Before fetching anything, read the existing reference file:

```
~/.claude/skills/db-scalability-audit/references/provider-limits.md
```

Note which limits look potentially stale (pricing especially changes frequently), and which source URLs are listed per provider. These are the authoritative sources to re-fetch.

---

## Step 2 — Fetch provider documentation

Fetch each URL below. Extract only the specific limits listed — skip marketing copy. If a fetch fails, note it in the update log and continue.

### Cloudflare D1

| URL | What to extract |
|-----|----------------|
| `https://developers.cloudflare.com/d1/platform/limits/` | Storage limits per plan, row limits per query, query duration limits, max databases per account |

### Supabase

| URL | What to extract |
|-----|----------------|
| `https://supabase.com/pricing` | Plan names and prices, storage per plan, compute specs per plan |
| `https://supabase.com/docs/guides/platform/limits` | Connection limits (direct + pooler), row limits, storage limits, HIPAA/SOC2 availability per plan |
| `https://supabase.com/docs/guides/database/connecting-to-postgres` | Pooler modes (Transaction vs Session), recommended connection strings for serverless runtimes |

### Neon

| URL | What to extract |
|-----|----------------|
| `https://neon.tech/pricing` | Plan names, prices, storage per plan, compute specs |
| `https://neon.tech/docs/introduction/plans` | Detailed per-plan limits, HIPAA availability |
| `https://neon.tech/docs/connect/connection-pooling` | Pooling guidance for serverless runtimes |

### PlanetScale

| URL | What to extract |
|-----|----------------|
| `https://planetscale.com/pricing` | Plan names, prices, storage, connection limits, HIPAA availability |

### AWS RDS / Aurora

| URL | What to extract |
|-----|----------------|
| `https://aws.amazon.com/rds/postgresql/pricing/` | Instance types and minimum cost for Postgres |
| `https://aws.amazon.com/rds/aurora/pricing/` | Aurora Serverless v2 ACU pricing, minimum cost |
| `https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html` | Scaling behavior, minimum ACU, cold start characteristics |

### Turso

| URL | What to extract |
|-----|----------------|
| `https://turso.tech/pricing` | Plan names, prices, storage per DB, replica locations, HIPAA availability |

---

## Step 3 — Diff against current file

For each provider, compare fetched values against what's in `provider-limits.md`. Build a change list:

- Numbers that changed (storage caps, prices, connection limits)
- Plans that were added or renamed
- HIPAA/compliance availability changes (these matter for healthcare projects)
- Anything in the current file that could not be verified from the fetched source

---

## Step 4 — Update provider-limits.md

Rewrite only the sections that changed. Rules:

- Every provider section must have a `**Source:**` block listing the URLs used, with the date verified
- If a value could not be confirmed from the fetched source, mark it `[unverified — check manually]` rather than leaving a stale number
- If a plan was discontinued or renamed, update it and note the change
- Do not remove providers — even if a provider seems less relevant, keep it for completeness
- Keep the file under 400 lines; if it would exceed that, trim "Key notes" sections to the most important 3 bullets per provider

Update the `Last updated:` line at the top of the file to today's date.

---

## Step 5 — Write an update log

Create or overwrite `~/.claude/skills/db-scalability-audit/references/update-log.md`:

```markdown
# DB Scalability Audit Skill — Update Log

**Date:** <YYYY-MM-DD>

## Sources fetched successfully
- <URL> — <one line on what was verified or updated>

## Sources that failed
- <URL> — <HTTP status or error>

## Changes made
- <provider> — <what changed: old value → new value>

## Values that could not be verified
- <provider.field> — <reason: 404, paywalled, restructured page, etc.>

## Recommended follow-up
- <anything requiring manual verification>
```

---

## Constraints

- Only write to `~/.claude/skills/db-scalability-audit/references/`
- Never modify `SKILL.md` or its frontmatter
- Only update values drawn from fetched sources — do not guess or fill in from training data
- Where a source failed to load, mark the affected values as `[unverified]` rather than leaving potentially stale numbers
