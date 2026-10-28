---
name: write-tests
description: >
  Write high-quality tests following a research-backed philosophy: tests as
  executable specifications of observable behaviour, doubles only at real
  boundaries, deterministic and order-independent, with oracles that can
  actually fail. Use this skill whenever the user asks to write tests, add test
  coverage, review what should be tested, or wants help thinking through a test
  suite. Also trigger when the user shares code and asks "should I test
  this?", "how do I test this?", "what am I missing in my tests?", or "write
  tests for X". Don't wait for the user to say "write-tests" explicitly.
  For auditing an existing suite, use /test-health instead.
---

# Write Tests

Tests are executable specifications. Identify the contract the code promises,
then encode that contract as tests that can fail when the contract breaks and
give the same answer every time.

The rules below are numbered T1–T39. Their reasoning, sources and the
disagreements between authorities are in
[`references/test-philosophy.md`](references/test-philosophy.md). Read the
theme for the decision you are making; do not load the whole file for a small
test.

| Theme | Heuristics | Read it when |
|-------|------------|--------------|
| A test is a specification a client could read | T1–T7 | Always, before Step 3 |
| Doubles belong at boundaries the client can observe | T8–T15 | The code has a dependency you might replace |
| Determinism is enforced by tooling | T16–T22 | The test touches time, I/O, async, shared state |
| Suite shape and UI tests | T23–T27 | Choosing a level, or testing UI |
| The oracle decides whether a pass means anything | T28–T36 | Always, before Step 6 |
| Properties generalise examples | T37–T39 | The contract is "for all inputs" |

## Step 0 — Load the project's testing conventions

Project rules override the generic defaults here. Before writing anything,
find and read them:

- `CLAUDE.md` files and their testing sections, `.claude/rules/testing.md` if
  present, and any ADR whose title mentions tests, mocks, isolation or
  fixtures.
- The harnesses the suite already runs inside: network/socket guards,
  console-output guards, request-mocking setup (e.g. MSW handlers), database
  isolation, randomised or parallel execution, CI-only retries. Note what each
  one enforces so the new test works inside it rather than around it.
- Naming and location conventions for test files, and any lint rule or
  pre-commit hook that enforces them.

If a project convention contradicts a T-rule, follow the project and say so in
the output.

## Step 1 — Get the code and the existing tests

Read the code under test. Then search for tests that already cover it. Do not
guess file names; search for the module, class and function names across the
test directories, in every language the repo uses.

List what is already covered before writing a single new test. Fill gaps; do
not duplicate.

## Step 2 — Identify the contract

Answer *what does this code promise to a caller?* (T1). The contract has three
parts:

- **Postconditions:** what is guaranteed on return. Always test these.
- **Invariants:** what must hold after every mutating operation.
- **Boundary contracts:** the shape one module expects from another. Test
  these in integration tests, not in each unit.

Do not test preconditions past the point the code rejects bad input. Do not
test implementation details: ask "would a caller notice if this changed?"
(T1, T7). Prefer output-based assertions over state, and state over
interaction checks (T7).

## Step 3 — Let types carry what they can

Before writing a test, ask whether a type can enforce the constraint instead.
A test of something a type already guarantees tests the type checker.

| Constraint | Type-expressible as |
|------------|--------------------|
| "status is one of four values" | a `Literal` / union with an exhaustive `match` |
| "these fields only exist together" | a discriminated union |
| "the score is between 0 and 1" | a constrained type (`Field(ge=0, le=1)`, `z.number().min(0).max(1)`) |
| "this string is a validated email" | a branded type produced by a parse function |

If the project has `/type-health`, its heuristics are the fuller version of
this table. Rules over histories or relationships between records ("never more
than N per week", "idempotent on this key") are beyond types; they belong in
Step 5's property tests.

## Step 4 — Choose the level and the doubles

**Level** (T23–T24): pick the lowest level that can catch the failure. Unit
tests specify one unit's behaviour; integration tests specify the boundary
between modules, not the units again; end-to-end tests cover only critical user
flows. Classify by what the test touches (process, network, disk), not only by
scope.

**Doubles** (T8–T15), in order of preference:

1. The real implementation, if it is fast and deterministic.
2. A fake the project owns and has checked against the real thing (T14).
3. A stub that feeds inputs. Never assert on a stub (T10).
4. A mock that verifies an outgoing call, only for an unmanaged out-of-process
   dependency whose side effect a client would observe (T9).

Also:

- Do not mock types you do not own; wrap them in an adapter you own and double
  that (T11).
- Constrain every double to the real API: `create_autospec` / `spec_set` in
  Python, typed doubles in TypeScript (T12). An unspecced mock accepts calls
  the real object would reject.
- On the frontend, mock at the network boundary (e.g. MSW), not your own API
  client module (T13).
- Prefer an injected seam over patching a module global (T15).

If isolating the unit needs many doubles, stop and report it as a design
signal (Step 7) before writing workaround tests.

## Step 5 — Write the tests

- One behaviour per test: one Act, any number of related assertions (T2).
- Name the test as a sentence about the behaviour and its outcome
  (T3): `test_withdraw_never_makes_balance_negative`, not `test_withdraw`.
- Straight-line code: no `if`, loops or computed expectations in the body. Use
  parametrisation tables (`pytest.mark.parametrize`, `it.each`) (T4).
- Show the inputs that matter; hide irrelevant construction in builders (DAMP
  over DRY, T5). Make failure output state expected, actual and parameters
  (T6).
- **UI:** query by role and accessible name first (T25). Wait for an observable
  outcome (`findBy*`, `waitFor`) rather than a fixed delay; treat an `act()`
  warning as a bug in the test (T26). Do not leave unexpected console output
  (T27).
- **Properties** (T37–T39): when the contract is "for all inputs" (round-trips,
  invariants under any sequence of operations, algebraic laws, model or
  reference agreement, rules over histories), write a property test with
  Hypothesis or fast-check. Constrain generators to the legal domain instead
  of filtering, check the generators produce interesting values, and keep a
  couple of example tests for known-tricky cases. "Doesn't crash" is not an
  oracle on its own. If the project lacks the library, say so and write the
  example-based version; do not add a dependency as a side effect.

Framework defaults, if the project does not say otherwise: Python uses pytest
with fixtures; TypeScript uses Vitest or Jest; anything else, state the
assumption.

## Step 6 — Make sure each test can fail and is deterministic

A test you have only seen pass is unverified.

- **See it fail** (T28): break the behaviour (invert a condition, return early,
  drop a call) or run the test before the fix, and confirm it goes red for the
  right reason. Revert the break.
- **Exceptions** (T29): assert the specific type and a message match. Never
  `pytest.raises(Exception)` or a bare `toThrow()` around code that can fail
  for other reasons.
- **Negative assertions** (T30): "X did not happen" must run after X had its
  chance. Anchor it on a positive event that happens at the same time (the
  request that did go out, the element that did render), or it passes
  vacuously.
- **Determinism** (T16–T20): no real network or clock, no bare sleeps, seeded
  randomness, no reliance on collection or test order. Reset any state the
  runner does not reset for you.
- Run the new tests in random order and in parallel if the project supports it
  (T17), and several times if they involve async or timing.

## Step 7 — Surface design signals

If a test is hard to write, say so before writing workarounds:

| Symptom | Likely cause |
|---------|-------------|
| Needs many doubles to isolate | Too many dependencies; split responsibilities |
| Hard to name in one sentence | The unit does more than one thing |
| Must reach into internal state to assert | Testing implementation, or a missing query on the API |
| Setup longer than the assertion | Missing abstraction or a bad boundary |

The user may prefer to refactor first.

## Output format

1. **Contract:** one short paragraph on what the code promises.
2. **Tests:** idiomatic, minimal, ready to run, with the commands you ran.
3. **Verification:** how you saw each test fail (Step 6), and whether it ran
   shuffled or in parallel.
4. **Design signals:** only if present.
