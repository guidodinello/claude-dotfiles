# Worked example - an analytics column-privacy policy

> **Purpose**: a complete `/design-review` report in the exact output format of
> SKILL.md Step 6. The change is synthetic: names, paths, and counts are
> illustrative, and no real system, client, or person is described.
>
> **Context for the reader of this example**: a nightly ETL copies records
> from an EHR into a reporting database used by a BI tool. The PR adds a
> per-column privacy policy. Each column is KEEP (copied as-is), HIDE (loaded
> as null), or DERIVE (replaced by an allowlisted subset, for example only
> `status` and `changed_at` from each entry of a status-history array).

---

## Design review - Add column-privacy policy to the reporting ETL (#123)

**Summary.** The PR declares a KEEP / HIDE / DERIVE policy for every column of
the ETL's reporting entities, directly on the ORM entity, and enforces it in
the one base class every load extends. Hidden columns arrive as null and
derived columns as an allowlisted, scalar-only subset. Drift and snapshot
tests, a post-map assertion, and boot-time checks hold the policy in place.

### 1. Decisions

#### D1 - Policy declared on the entity through custom decorators

- **Chose:** `@HiddenColumn()` and `@DerivedColumn(deriver)` wrap the ORM's
  column decorator, force the database column comment, and register the
  column in a registry keyed by entity class (`etl/policy/decorators.ts`,
  `etl/policy/registry.ts`). 56 entity columns are annotated.
- **Rejected:** a separate list of hidden columns - a second source of truth
  that drifts from the entities (explicit, PR description).
- **Rejected:** keying the policy on the column comment text - it failed open:
  a comment one character off silently loaded real data, and it tied behavior
  to documentation wording (explicit, PR description).
- **Why:** the policy must not be forgettable when a column is added; putting
  it on the column makes adding a column without a policy decision visible in
  review and detectable by a test.

#### D2 - Enforcement at a single choke point, with independent second checks

- **Chose:** `BaseLoad.run()` applies the policy to the raw DTO before
  mapping; a post-map assertion checks that every hidden column is null; boot
  checks refuse to start if a dedupe key is a hidden or derived column
  (`etl/loads/base-load.ts`, `etl/policy/boot-checks.ts`).
- **Rejected:** applying the policy in each load's mapper (implied) -
  repeated per load and skippable by a new one.
- **Why:** every load already extends `BaseLoad`, so one call site covers all
  current and future loads.

#### D3 - Derivers parse unknown input into a precise output type

- **Chose:** derivers take `unknown`, narrow it, and return `DerivedValue`;
  allowlists keep only scalar values, so a nested object or free-text field is
  dropped (`etl/policy/derivers.ts`).
- **Rejected:** typing derivers against the source record shape (implied) -
  the source is untyped JSON from the EHR, so the type would be a claim, not a
  proof.
- **Why:** a deriver is the last thing between raw clinical data and the
  reporting database; it must fail closed on shapes it does not recognize.

### 2. Quality attributes

| Decision | Attribute (ISO/IEC 25010) | Where the code delivers it | Principle |
|----------|---------------------------|----------------------------|-----------|
| D1 | Security / Confidentiality | Registry is the only input to the filter; an unregistered column cannot be "hidden by accident", and the drift test catches an undecorated one | P1 Fail-safe defaults |
| D1 | Maintainability / Modifiability | Policy lives on the column it governs; the deriver sits next to its column (`@DerivedColumn(statusHistoryDeriver)`) | P14 One authoritative representation, P15 Locality of behaviour |
| D2 | Security / Confidentiality | `BaseLoad.run()` is the single path from raw DTO to mapper | P2 Complete mediation |
| D2 | Reliability / Faultlessness | Post-map assertion and boot checks fail the run instead of loading wrong data | P5 Separation of privilege (the post-map assertion is a second, independent check) |
| D3 | Security / Confidentiality | Scalar-only allowlist drops nested free text | P1 Fail-safe defaults |
| D3 | Maintainability / Analysability | `DerivedValue` tells the mapper exactly what a derived column contains | P9 Parse, don't validate |

### 3. Trade-offs

| Decision | Cost | Accepted because |
|----------|------|------------------|
| D1 | A custom decorator the team must learn; 56 entity columns touched in one PR | One source of truth beats a parallel list (P14); the churn is one-time |
| D1 | Couples the ORM entities to the ETL policy module | The entities exist only for the reporting database |
| D2 | Every load pays the filter and the post-map assertion | Per-row cost is small next to the nightly batch's I/O |
| D3 | One `as` cast remains in the function that builds the policed DTO from runtime keys | Keeps the downstream mapper fully typed; the cast is confined to one function |

### 4. Invariants and their guards

| Invariant | Guard | Kind | Fitness function? |
|-----------|-------|------|-------------------|
| Every policy column is decorated and carries its comment | Drift test over all entity metadata | Test | Yes - shown failing by temporarily removing a decorator |
| The full policy map matches the agreed spreadsheet | Expected-policy snapshot test | Test | Yes |
| A derived column has a deriver | `@DerivedColumn(deriver)` requires the argument | Type (compile time) | Yes - the illegal state is unrepresentable (P8) |
| Hidden columns are null after mapping | Post-map assertion in `BaseLoad.run()` | Runtime assertion | Yes - fails the run |
| A dedupe key is never a hidden or derived column | Boot check | Boot-time check | Yes |
| Every load extends `BaseLoad` | None | Convention only | No |

**Unguarded:** "every load extends `BaseLoad`" - see R1.

### 5. Risks and open questions

- **R1 - A load that bypasses `BaseLoad` skips the policy.** All current loads
  extend it, but nothing stops a new one from writing to the reporting database
  directly. Principle: Complete mediation (P2, [Saltzer & Schroeder](https://www.cs.virginia.edu/~evans/cs551/saltzer/))
  and Guard each invariant with a fitness function (P10, [Thoughtworks Radar](https://www.thoughtworks.com/radar/techniques/architectural-fitness-function)).
  Question for the team: add a test that every class registered as a load is a
  `BaseLoad` subclass, or accept the convention?
- **Q1 - Column comments are now user-facing text.** The BI tool surfaces
  column comments as field descriptions, so the forced comment was rewritten
  for that reader ("Hidden by design: always empty, kept out of reporting to
  protect patient data."). Since the policy is keyed on the decorator, not the
  text (P7), rewording is safe; the open question is who owns that copy.

Coverage: read the full diff, the PR description, `BaseLoad` and three
existing loads, and the ORM column decorator. Did not read the BI tool's
configuration or run the tests.
