# Database Provider Limits Reference

Last updated: 2026-04-16

All limits and pricing in this file must be verified against the linked source before being cited in a report. Provider docs change without notice — if a source link is dead or the numbers differ from what you observe, update the file and note the discrepancy in the meta skill's update log.

---

## Cloudflare D1

**Source:** https://developers.cloudflare.com/d1/platform/limits/ (verified 2026-04-16)

| Limit | Free | Paid (Workers Paid Plan) |
|---|---|---|
| Max database size | 500 MB | 10 GB |
| Max storage per account | 5 GB | 1 TB |
| Databases per account | 10 | 50,000 |
| Rows returned per query | [unverified — check manually] | [unverified — check manually] |
| Rows per table | Unlimited | Unlimited |
| Queries per Worker invocation | 50 | 1,000 |
| Query duration | 30 s | 30 s |
| Max SQL statement length | 100 KB | 100 KB |
| Max bound parameters per query | 100 | 100 |
| Max string/BLOB/row size | 2 MB | 2 MB |
| Columns per table | 100 | 100 |
| Time Travel (PITR) | 7 days | 30 days |
| Concurrent connections | Managed by CF | Managed by CF |
| Read replicas | No | No |
| Transactions | Yes (serializable) | Yes (serializable) |
| Full-text search | Basic (SQLite FTS5) | Basic (SQLite FTS5) |

**Key notes:**
- D1 is SQLite under the hood — SQL dialect is SQLite, not Postgres
- No native connection pooling needed (Workers manage connections per Worker instance)
- No `pg_*` extensions; no horizontal scaling (read replicas, sharding)
- At 10 GB hard limit, the DB becomes read-only — writes are rejected
- Time Travel provides point-in-time restore (30 days on paid, 7 days free); no longer requires manual wrangler export

**When D1 is the wrong choice:**
- DB approaching 5+ GB (safety margin before 10 GB hard cap)
- Need for Postgres-specific features (JSONB operators, CTEs with `RETURNING`, window functions, pg extensions)
- High write throughput (D1 is optimized for read-heavy workloads)

---

## Supabase Postgres

**Sources:**
- https://supabase.com/pricing (failed to load 2026-04-16 — values below unverified)
- https://supabase.com/docs/guides/platform/limits (404 on 2026-04-16 — values below unverified)
- https://supabase.com/docs/guides/database/connecting-to-postgres (verified 2026-04-16)

| Limit | Free | Pro ($25/mo) | Team ($599/mo) | Enterprise |
|---|---|---|---|---|
| Storage included | 500 MB | 8 GB [unverified] | 28 GB [unverified] | Custom |
| Connections (direct) | 60 [unverified] | 120 [unverified] | 480 [unverified] | Custom |
| Connections (via pooler) | Up to 200 [unverified] | Up to 200+ [unverified] | Custom | Custom |
| Compute (free) | Shared (micro) [unverified] | Dedicated [unverified] | Custom [unverified] | Custom |
| Read replicas | No [unverified] | No [unverified] | Yes [unverified] | Yes |
| Point-in-time recovery | No [unverified] | No [unverified] | 7 days [unverified] | Custom |
| Daily backups | 7 days [unverified] | 7 days [unverified] | 14 days [unverified] | Custom |
| HIPAA BAA | No [unverified] | No [unverified] | Yes [unverified] | Yes |
| SOC 2 Type II | No [unverified] | No [unverified] | Yes [unverified] | Yes |

**Key notes:**
- Full Postgres — all extensions, standard SQL, `pg_` functions work
- Free tier projects pause after 1 week of inactivity [unverified — check manually]
- Direct connection limit is low; use PgBouncer (built-in on all plans) or Supabase Pooler (Supavisor)
- HIPAA add-on requires Team plan or higher + signed BAA [unverified — check manually]

**Connection guidance for serverless (verified):**
Use pooler connection string in Transaction mode (port 6543) from serverless runtimes (Cloudflare Workers, Vercel Edge, Lambda). Session mode uses port 5432 and is for persistent backends needing IPv4. Direct connections from serverless will exhaust the connection limit under concurrent load.

---

## Neon (Serverless Postgres)

**Note:** Neon migrated from neon.tech to neon.com (308 permanent redirect as of 2026-04-16).

**Sources:**
- https://neon.com/pricing (verified 2026-04-16)
- https://neon.com/docs/introduction/plans (verified 2026-04-16)
- https://neon.com/docs/connect/connection-pooling (verified 2026-04-16)

| Limit | Free | Launch (pay-per-use) | Scale (pay-per-use) |
|---|---|---|---|
| Storage | 0.5 GB/project | $0.35/GB-month | $0.35/GB-month |
| Compute | 100 CU-hr/mo, up to 2 CU (8 GB RAM) | $0.106/CU-hr, up to 16 CU (64 GB RAM) | $0.222/CU-hr, up to 56 CU (224 GB RAM) |
| Branching | 10 branches/project | 10 branches/project | 25 branches/project |
| Read replicas | Yes (count as CU-hrs) | Yes | Yes |
| Point-in-time recovery | 6 hours (capped at 1 GB) | Up to 7 days ($0.20/GB-month) | Up to 30 days ($0.20/GB-month) |
| HIPAA BAA | No | No | Yes (additional charge) |
| SOC 2 / ISO 27001 | No | No | Yes |
| Auto-suspend | 5 min (mandatory) | 5 min (disableable) | Fully configurable (1 min to always-on) |
| Projects max | 100 | Unlimited | 1,000 (soft limit, increasable) |

**Key notes:**
- Neon has moved to pay-per-use pricing — no fixed monthly fees for Launch or Scale
- HIPAA moved from the old Business plan ($700/mo) to Scale (pay-per-use + additional charge)
- PgBouncer connection pooling in Transaction mode only — add `-pooler` to hostname for serverless
- HTTP-based query API available (good for edge runtimes that can't use TCP)
- Cold starts still a concern on Free plan (mandatory auto-suspend after 5 min)

**Connection guidance for serverless (verified):**
Add `-pooler` to your endpoint hostname. Neon uses PgBouncer in Transaction mode exclusively — connections return to pool after each transaction. `SET`, `LISTEN/NOTIFY`, temp tables with session flags, and `PREPARE` are not supported in pooled connections. For schema migrations and `pg_dump`, use direct connections.

---

## PlanetScale

**Source:** https://planetscale.com/pricing (verified 2026-04-16)

**Note:** PlanetScale completely restructured pricing as of 2026. The old consumer tier plans (Hobby, Scaler, Scaler Pro) no longer exist. Pricing is now infrastructure-based (cluster size + storage + optional add-ons) for both Postgres and Vitess offerings.

**Postgres pricing (EBS HA, 3-node: primary + 2 replicas):**

| Cluster size | Starting price |
|---|---|
| PS-5 | $15/month |
| PS-2560 | $5,599/month |

**Postgres pricing (EBS non-HA, single node):**

| Cluster size | Starting price |
|---|---|
| PS-5 | $5/month |
| PS-2560 | $1,867/month |

**Vitess pricing (non-metal, 3-node):**

| Cluster size | Starting price |
|---|---|
| PS-10 | $39/month |
| PS-2800 | $7,199/month |

- Storage, VTGates, replicas, and sharding are priced separately
- HIPAA availability: not mentioned in current pricing page [unverified — check manually]
- Available in 20+ regions across AWS and GCP

**Key notes:**
- Vitess is MySQL-compatible — foreign key enforcement off by default; not compatible with Postgres-specific SQL
- PlanetScale now offers native Postgres (via EBS clusters) in addition to Vitess
- Schema migrations on Vitess are online and non-blocking
- Old plan names (Hobby, Scaler, Scaler Pro) are discontinued

---

## AWS RDS Postgres / Aurora Serverless v2

**Sources:**
- https://aws.amazon.com/rds/postgresql/pricing/ (verified 2026-04-16)
- https://aws.amazon.com/rds/aurora/pricing/ (verified 2026-04-16)
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html (verified 2026-04-16)

| Feature | RDS Postgres | Aurora Serverless v2 |
|---|---|---|
| Scaling | Manual instance resize | Auto-scales in 0.5 ACU increments |
| Storage | Up to 64 TB | Up to 128 TB |
| Read replicas | Up to 15 | Up to 15 |
| HIPAA BAA | Yes (via AWS BAA) | Yes |
| Min cost | ~$15-30/mo (db.t3.micro) | ~$43/mo (0.5 ACU × $0.12/hr × 24h × 30d) |
| ACU pricing | N/A | $0.12/ACU-hr (Standard); $0.156/ACU-hr (I/O-Optimized) |
| Connection pooling | RDS Proxy (additional cost) | RDS Proxy (additional cost) |
| Cold start | N/A | Scales without disruption; pause/resume available |

**Key notes:**
- Best-in-class compliance (HIPAA, SOC 2, PCI, etc.)
- Requires VPC setup — adds operational complexity vs. managed Supabase/Neon
- RDS Proxy needed for serverless runtimes (Lambda, Workers) to avoid connection exhaustion
- Aurora Serverless v2 does not truly scale to zero at default config — minimum 0.5 ACU costs ~$43/mo
- Scaling in Aurora Serverless v2 happens without disrupting running transactions (unlike v1)
- Operational overhead is significantly higher than Supabase or Neon

---

## Turso (SQLite-compatible, libSQL)

**Source:** https://turso.tech/pricing (verified 2026-04-16)

| Limit | Free | Developer ($4.99/mo) | Scaler ($24.92/mo) | Pro ($416.58/mo) |
|---|---|---|---|---|
| Databases | 100 | Unlimited | Unlimited | Unlimited |
| Monthly Active DBs | N/A | 500 | 2,500 | 10,000 |
| Total account storage | 5 GB | 9 GB (+$0.75/GB overage) | 24 GB (+$0.50/GB overage) | 50 GB (+$0.45/GB overage) |
| Replica locations | [unverified — check manually] | [unverified — check manually] | [unverified — check manually] | [unverified — check manually] |
| HIPAA BAA | No | No | No | Yes |

**Key notes:**
- libSQL fork of SQLite — closest drop-in replacement for D1
- Plans changed significantly: old Starter ($29/mo) and old Scaler ($259/mo) replaced by Developer ($4.99), new Scaler ($24.92), and Pro ($416.58)
- Storage quota is total account storage, not per-database
- Edge-native: replicas can be placed close to users globally
- Easier D1 migration path than Postgres (SQLite dialect compatibility)
- Less mature ecosystem than Postgres alternatives
