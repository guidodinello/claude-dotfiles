---
name: write-tests
description: >
  Write high-quality tests following a spec-driven philosophy: tests as executable specifications,
  testing behavior not implementation, with clear thinking about what belongs in types vs tests vs
  runtime guards. Use this skill whenever the user asks to write tests, add test coverage, review
  what should be tested, or wants help thinking through a test suite. Also trigger when the user
  shares code and asks "should I test this?", "how do I test this?", "what am I missing in my
  tests?", or "write tests for X". Don't wait for the user to say "write-tests" explicitly —
  trigger whenever someone needs tests written or wants to reason about test coverage for a
  non-trivial piece of code.
---

# Write Tests

Tests are executable specifications. Your job is to identify the contract this code promises,
then encode that contract as tests — nothing more, nothing less.

## Step 1 — Get the code

If the user provided a file path, read it. If they pasted code inline, work from that. If
neither, ask for the code before proceeding.

**Always search for existing tests before writing anything.** Use grep and find — don't rely
on guessing filenames, because test files often have suffixes or live in unexpected locations:

```bash
# Find any test file that imports or references the target module/function
grep -r "<module_or_function_name>" tests/ --include="*.py" -l 2>/dev/null
# Also look for naming variants
find . -name "test_*<module_stem>*" -o -name "*<module_stem>*_test*" 2>/dev/null | grep -v __pycache__
```

Read every file you find. Explicitly list what's already covered before writing a single new
test — this prevents duplicating tests that already exist and ensures you only fill real gaps.

## Step 2 — Identify the contract

Before writing a single test, answer: *what does this code promise?*

The contract has three parts, each with different testing obligations:

**Postconditions** — what the function/class guarantees on return. Always test these.
Examples: "returns a sorted list", "the record is persisted", "the result is always ≥ 0".

**Class/data invariants** — properties that must hold on an object at all times. Test these
after every mutating operation.
Examples: "balance is never negative", "the queue never exceeds max_size".

**Boundary contracts** — for integration tests, the interface assumptions between modules.
Test these when two pieces compose, not when testing each unit alone.
Examples: "the repository returns items in the shape the service expects".

**Do not test preconditions** — things the caller must ensure. If a function requires
non-negative input and the behavior on negative input is undefined, don't test the undefined
path. You may test that the function *rejects* bad input (raises an error), but not behavior
past the error point — that belongs to the caller's tests.

## Step 3 — Check the type system first

Before writing a test, ask: *can a type enforce this constraint instead?*

If yes, the test is redundant — the type-checker is exhaustive and can't be bypassed. Only
write tests for things types can't express: behavior, sequencing, temporal ordering, runtime
values, business rules.

Types absorb more than shape. Before concluding a constraint needs a test, check whether it is:

| Constraint | Type-expressible as |
|------------|--------------------|
| "status is one of four values" | a `Literal` / union — and an exhaustive `match` |
| "these fields only exist together" | a discriminated union |
| "the score is between 0 and 1" | a constrained type (`Annotated[float, Field(ge=0, le=1)]`, `z.number().min(0).max(1)`) |
| "the vector has 512 elements" | a length-constrained type |
| "this string is a validated email" | a branded/refined type produced by a parse function |

A test asserting one of those is a test of the type checker, not of your code. If the project
has a `/type-health` skill, its heuristics (H1–H11) are the fuller version of this table —
consult it when the answer is "maybe".

## Step 3b — Properties over examples

Some contracts are true for *all* inputs, not for the three you thought of. When a
postcondition or invariant from Step 2 is universally quantified — "for any input, X holds" —
an example-based test samples it; a property-based test searches it.

Reach for property-based testing (`hypothesis` in Python, `fast-check` in TS/JS) when the
contract has this shape:

- **Round-trips** — `decode(encode(x)) == x` for any `x`
- **Invariants under operation** — the balance is never negative *after any sequence* of
  deposits and withdrawals; the queue never exceeds `max_size`
- **Algebraic laws** — sorting is idempotent; a merge is commutative; a normalizer applied
  twice equals applied once
- **Relations between two implementations** — the fast path always agrees with the slow one
- **Rules over sequences of states or across records** — "never more than N per week",
  "an item once shown is not shown again inside the cooldown window", "the operation is
  idempotent on this key"

That last row is the important one, and it's where types stop entirely. A type constrains a
*value*; these constrain a *history* or a *relationship between records*. No type system in a
mainstream language reaches them — this is the territory formal specification languages
(TLA+, Alloy) were built for, and property-based tests are the affordable approximation.

Practical rules:

- Write the property as the test name: `test_cooldown_never_repeats_within_window`.
- Constrain generators to the legal input domain rather than filtering inside the test —
  a heavily-filtered generator is a slow generator.
- Keep a couple of example-based tests alongside the property for the known-tricky cases;
  properties prove the general rule, examples document the specific bug you once had.
- When a property fails, the shrunk counterexample *is* the bug report — quote it verbatim.

Don't force it. A function with one input and one obvious output does not need a property;
reserve this for contracts where "for all" is genuinely the claim.

## Step 4 — Choose the right level

| Level | Spec being tested | Rule |
|-------|-------------------|------|
| Unit | Function/class contract in isolation | Dependencies are faked/mocked; test one unit's promises |
| Integration | Boundary contract between two modules | Don't re-test the units; test the interface assumptions |
| E2E | Product behavior from the user's perspective | Critical flows only; expensive, keep few |

Don't duplicate across levels. If a unit is already tested, the integration test should verify
the *boundary*, not re-verify the unit's internals. If the integration is already tested, E2E
tests verify user-visible outcomes, not internal wiring.

## Step 5 — Write the tests

Structure each test around one concept, not one function. A concept might require several
assertions, but a function might have several independent behaviors worth separate tests.

Naming: test names should prove something. `test_withdraw_never_makes_balance_negative` is
a spec. `test_withdraw` is a label.

Avoid asserting on implementation details. If you refactor internals and a test breaks without
any behavior changing, that test was speccing the wrong thing. Ask: "would a caller care if
this changed?" If no, don't assert on it.

For data-heavy cases, prefer parametrize/table-driven patterns over repeated identical tests.

**Framework defaults** (infer from imports/config first):
- Python → `pytest` with fixtures; `hypothesis` for Step 3b properties
- TypeScript/JavaScript → `vitest` or `jest`; `fast-check` for Step 3b properties
- Other → state your assumption before writing

If a property test needs a dependency the project doesn't have yet, say so and write the
example-based version — don't add a dependency as a side effect of writing tests.

## Step 6 — Surface design signals

If a test is hard to write, say so explicitly — this is diagnostic information, not just an
obstacle.

| Symptom | Likely cause |
|---------|-------------|
| Requires many mocks to isolate | Too many dependencies; single-responsibility violation |
| Hard to name the test clearly | The function does more than one thing |
| Must expose internal state to assert on it | Testing implementation, not behavior |
| Setup is longer than the assertion | Missing abstraction or bad boundary |

Surface these before writing workaround tests. The user may prefer to refactor first.

## Output format

1. **Contract** — one short paragraph: what does this code promise?
2. **Tests** — idiomatic, minimal, ready to run
3. **Design signals** (only if present) — a short note on what's hard to test and why

Keep the contract section tight. The tests should speak for themselves.
