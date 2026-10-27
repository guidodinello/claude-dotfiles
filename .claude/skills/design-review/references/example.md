# Worked example - payment idempotency keys

> **Purpose**: a complete `/design-review` report in the exact output format of
> SKILL.md Step 6. The change is synthetic: names, paths, and numbers are
> illustrative, and no real system, client, or person is described.
>
> **This is a format reference, not an answer key.** Its decisions, guards,
> and findings belong to this invented change. Do not look for them in the PR
> under review; derive every entry from that PR's own diff and description.
>
> **Context for the reader of this example**: a payments API calls an external
> card processor. Mobile clients retry on timeouts, and some retries produced
> double charges. The PR adds an `Idempotency-Key` header to the payment
> endpoints.

---

## Design review - Add idempotency keys to the payments API (#482)

**Summary.** The PR adds an `idempotency_keys` table and a middleware on the
payments router. The first request with a key records it as pending in the
same transaction that starts the charge; a retry with the same key and body
replays the stored response, a concurrent one gets 409, and a reuse with a
different body gets 422. Requiring the header is behind a flag until client
SDKs send it.

### 1. Decisions

#### D1 - Keys persisted in the primary database with a unique index

- **Chose:** a table `idempotency_keys (client_id, key, request_hash, state,
  response)` with a unique index on `(client_id, key)`
  (`db/migrations/0142_idempotency_keys.sql`).
- **Rejected:** a cache entry with a TTL - evicted entries let a retry
  charge twice (explicit, PR description).
- **Rejected:** deduplicating on a hash of the request body alone - two
  legitimate identical payments would collide (implied).
- **Why:** the guarantee must survive restarts and replicas, and the database
  is already the transactional boundary of a payment.

#### D2 - Enforcement in one router middleware, opted into per route

- **Chose:** `idempotencyMiddleware` mounted on the payments router; each
  mutating route declares `idempotent: true` in its route options
  (`api/payments/router.ts`, `api/middleware/idempotency.ts`).
- **Rejected:** a check inside each handler (implied) - repeated, and a new
  handler can forget it.
- **Why:** one choke point that every payment mutation passes through.

#### D3 - A key is bound to a request fingerprint and fails closed on mismatch

- **Chose:** the first request stores `request_hash`; a later request with the
  same key and a different hash gets 422 and is not processed.
- **Rejected:** last write wins (implied) - a client bug reusing keys would
  silently drop a payment.
- **Why:** reusing a key for a different payment is a client error the API
  should surface, not guess around.

#### D4 - In-flight state as an explicit, constrained state machine

- **Chose:** `state` is `pending` or `completed`; the TypeScript type is a
  union where only `completed` carries `response`, and a `CHECK` constraint
  requires `response IS NOT NULL` when `state = 'completed'`. A concurrent
  duplicate of a `pending` key gets 409.
- **Rejected:** an in-process lock (implied) - does not hold across replicas.
- **Why:** a timeout during the processor call must leave a record a retry
  can reason about.

### 2. Quality attributes

| Decision | Attribute (ISO/IEC 25010) | Where the code delivers it | Principle |
|----------|---------------------------|----------------------------|-----------|
| D1 | Functional suitability / Functional correctness | Unique index makes a second charge for one key a constraint violation, not a race | P8 Make illegal states unrepresentable |
| D2 | Security / Integrity | Every route with `idempotent: true` passes through `idempotencyMiddleware` | P2 Complete mediation |
| D3 | Security / Integrity | Hash mismatch returns 422 before the handler runs | P1 Fail-safe defaults |
| D4 | Reliability / Fault tolerance | A retry after a processor timeout finds `pending` and gets 409 instead of charging again | - |
| D4 | Maintainability / Analysability | `IdempotencyRecord` union: a completed record without a response cannot be built | P8 Make illegal states unrepresentable |

### 3. Trade-offs

| Decision | Cost | Accepted because |
|----------|------|------------------|
| D1 | One extra write and index lookup per payment request | Payment volume is low next to the cost of a double charge |
| D2 | Tension P2 vs P15: a handler no longer shows that it is idempotent; the behavior lives in the middleware | The `idempotent: true` route option keeps a marker next to the route |
| D3 | Clients that re-serialize a body differently on retry get 422 (see R1) | Failing closed is safer than processing an ambiguous request |
| D4 | A crash between "pending" and "completed" blocks the key until the sweeper expires it | Clients get 409 and can retry with backoff |

### 4. Invariants and their guards

| Invariant | Guard | Kind | Fitness function? |
|-----------|-------|------|-------------------|
| At most one charge per `(client_id, key)` | Unique index | DB constraint | Yes |
| A completed record always has a stored response | `CHECK` constraint and the `IdempotencyRecord` union | DB constraint, Type | Yes |
| Every mutating payments route declares `idempotent: true` | `routes.idempotency.test.ts` | Test | Partly - runs in the `pre-push` hook only, not in CI, so `--no-verify` skips it |
| A `pending` key is resolved or expired within 15 minutes | Sweeper job in the worker process | Scheduled job | No - nothing alerts if the sweeper stops running |

**Unguarded:**

- **U1 - Pending keys can block forever.** If the worker is down, no request
  with a stuck key can complete. Principle: Guard each invariant with a
  fitness function (P10, [Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/architectural-fitness-function)).
  Cheapest guard: an alert on the age of the oldest `pending` row.
- **U2 - Route coverage test is skippable (partly guarded).** Running
  `routes.idempotency.test.ts` in the CI test job makes it automatic.
  Principle: P10, as above.

### 5. Risks and open questions

- **R1 - The fingerprint hashes raw bytes, not the parsed request.**
  `hashRequest()` in `api/middleware/idempotency.ts` hashes the raw JSON body,
  so a client retry that reorders keys or changes whitespace gets 422.
  Principle: Parse, don't validate (P9, [King](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)).
  Question for the team: hash the parsed, canonicalized payment request
  instead?
- **Q1 - Who turns on `REQUIRE_IDEMPOTENCY_KEY`, and when?** See section 6.
- Unguarded invariants: see section 4 (U1, U2).

### 6. Rollout and data migration

- **Deploy order:** migration `0142` (a new, empty table) runs before the app
  deploy; the middleware queries the table on every payment request.
- **Exposure window:** until `REQUIRE_IDEMPOTENCY_KEY` is on, requests without
  the header are processed without deduplication - today's behavior, so no
  regression, but no protection either.
- **Backfill:** none; keys apply only to new requests.

Coverage: read the full diff, the PR description, the payments router, two
handlers, and the worker's job registry. The linked ticket could not be
opened; worked from the PR text and code. Did not run the tests.
