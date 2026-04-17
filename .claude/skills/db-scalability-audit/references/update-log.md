# DB Scalability Audit Skill — Update Log

**Date:** 2026-04-16

## Sources fetched successfully

- https://developers.cloudflare.com/d1/platform/limits/ — Added account-level storage (1 TB paid / 5 GB free), queries-per-invocation limits, Time Travel PITR (30 days paid / 7 days free), max row/string/BLOB size (2 MB), max columns per table (100)
- https://supabase.com/docs/guides/database/connecting-to-postgres — Confirmed Transaction mode (port 6543) for serverless and Session mode (port 5432) for persistent backends; confirmed pooler recommendation for Cloudflare Workers and Vercel Edge
- https://neon.com/pricing — Verified full plan restructuring; confirmed pay-per-use model, storage pricing ($0.35/GB-month), compute pricing (Launch $0.106/CU-hr, Scale $0.222/CU-hr)
- https://neon.com/docs/introduction/plans — Verified detailed per-plan limits including PITR windows, auto-suspend behavior, compliance certifications, project limits
- https://neon.com/docs/connect/connection-pooling — Confirmed PgBouncer in Transaction mode only; confirmed `-pooler` hostname suffix pattern; confirmed limitations (no SET, no LISTEN/NOTIFY, no temp tables with session flags)
- https://planetscale.com/pricing — Verified complete plan restructuring to infrastructure-based pricing for Postgres and Vitess
- https://aws.amazon.com/rds/aurora/pricing/ — Confirmed ACU pricing: $0.12/ACU-hr (Standard), $0.156/ACU-hr (I/O-Optimized); confirmed 0.5 ACU minimum
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.html — Confirmed 0.5 ACU increments, non-disruptive scaling, scale-to-zero support
- https://aws.amazon.com/rds/postgresql/pricing/ — Confirmed free tier exists; specific instance pricing not extractable from page (recommends Pricing Calculator)
- https://turso.tech/pricing — Verified new plan structure, pricing, storage quotas (account-total, not per-DB), HIPAA on Pro only

## Sources that failed

- https://supabase.com/pricing — Page rendered empty (likely JavaScript-rendered content not accessible to fetcher)
- https://supabase.com/docs/guides/platform/limits — 404 Not Found; URL may have moved
- https://neon.tech/pricing — 308 Permanent Redirect to https://neon.com/pricing (re-fetched successfully)
- https://neon.tech/docs/introduction/plans — 308 Permanent Redirect to https://neon.com/docs/introduction/plans (re-fetched successfully)
- https://neon.tech/docs/connect/connection-pooling — 308 Permanent Redirect to https://neon.com/docs/connect/connection-pooling (re-fetched successfully)

## Changes made

- **D1** — Added account-level storage limits (5 GB free / 1 TB paid); added queries-per-invocation (50 free / 1,000 paid); added Time Travel PITR (7 days free / 30 days paid) replacing old "Not built-in" backup note; added max SQL statement length (100 KB), max bound parameters (100), max row size (2 MB), columns per table (100); rows per table updated to "Unlimited"
- **Neon** — Complete plan rewrite: old fixed-price plans (Free/$0, Launch/$19, Scale/$69, Business/$700) replaced with pay-per-use (Free/$0, Launch/pay-per-use, Scale/pay-per-use); HIPAA availability moved from Business ($700/mo) to Scale (pay-per-use + additional charge); PITR updated (Free now 6 hours, not 7 days); storage changed from fixed GB tiers to $0.35/GB-month; source URLs updated from neon.tech to neon.com
- **PlanetScale** — Complete section rewrite: old Hobby/Scaler/Scaler Pro tiers discontinued; replaced with infrastructure cluster pricing for Postgres (EBS HA from $15/mo, EBS non-HA from $5/mo) and Vitess (from $39/mo); noted that PlanetScale now offers native Postgres in addition to Vitess
- **Aurora Serverless v2** — Updated ACU pricing from estimate to exact values ($0.12/ACU-hr Standard, $0.156/ACU-hr I/O-Optimized); updated min cost to ~$43/mo with calculation shown; clarified scaling is non-disruptive (unlike v1)
- **Turso** — Complete plan rewrite: old Starter ($29/mo) and old Scaler ($259/mo) replaced by Developer ($4.99/mo), new Scaler ($24.92/mo), Pro ($416.58/mo); clarified storage is account-total (not per-DB); added Monthly Active DB limits per plan; HIPAA confirmed on Pro only

## Values that could not be verified

- **Supabase.connections_direct** — Pricing and limits pages failed to load; all connection limits marked [unverified]
- **Supabase.connections_pooler** — Same as above
- **Supabase.compute_specs** — Same as above
- **Supabase.storage_per_plan** — Same as above (Pro 8 GB / Team 28 GB from memory; unverified)
- **Supabase.read_replicas** — Same as above
- **Supabase.pitr** — Same as above
- **Supabase.hipaa_plan** — Same as above
- **Supabase.free_tier_pause** — Pause-after-inactivity behavior not confirmed from fetched source
- **D1.rows_returned_per_query** — New limits page does not list a per-query row return cap (old value was 100,000); marked [unverified]
- **Turso.replica_locations** — Not mentioned in current pricing page; marked [unverified]
- **PlanetScale.hipaa** — Not mentioned in current pricing page; marked [unverified]
- **RDS.min_instance_cost** — Exact instance pricing not extractable from pricing page (AWS recommends Pricing Calculator)

## Recommended follow-up

- **Supabase**: Visit https://supabase.com/pricing directly in a browser to verify current plan tiers, connection limits, and compute specs. Also check if the limits doc moved from /docs/guides/platform/limits.
- **D1 rows-per-query**: Check https://developers.cloudflare.com/d1/platform/limits/ directly to confirm whether the 100,000 rows-returned-per-query limit still applies or was removed.
- **Turso replica locations**: Visit https://turso.tech/pricing or https://docs.turso.tech/ to confirm replica location counts per plan.
- **PlanetScale HIPAA**: Check PlanetScale docs or contact sales to confirm HIPAA BAA availability on current plans.
- **Neon HIPAA cost**: The Scale plan lists HIPAA as available for an "additional charge" — verify the specific add-on cost at https://neon.com/pricing or by contacting Neon sales.
