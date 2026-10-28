---
name: test-health
allowed-tools: Bash Read Agent
description: >
  Audit an existing automated test suite against a research-backed set of
  heuristics (T1-T39): first whether the harnesses that keep tests honest
  exist and cover what they claim (network and console guards, random-order
  and parallel runs, visible retries, merged coverage), then tests that cannot
  fail, nondeterminism, doubles in the wrong place, and lower-severity smells.
  Use for a periodic test-suite health check, before a testing push, or when
  the user asks to "audit the tests", "review the test suite", "how healthy
  are our tests". Read-only: reports findings and proposes Issues; never edits
  tests. For writing new tests, use /write-tests.
---

# Test Health

Audit a test suite the way the evidence ranks problems: **can a test pass
while behaviour is wrong** (oracle) and **will it give the same answer every
time, in any order** (determinism) come first. Coupling, naming and structure
come after. Rule-based smell detectors misclassify heavily, so smells are
review prompts, not defects.

The heuristics, their sources, audit checks and severities are in the shared
reference `$HOME/.claude/skills/write-tests/references/test-philosophy.md`.
Read its "How to read the heuristics" section and Index before Step 1, and the
full file before Step 4. Use its severity vocabulary (High, Medium, Low, Info)
and verification tags unchanged.

Report structure follows `$HOME/.claude/guidelines/templates/audit-template.md`
when it exists.

**Read-only.** Probes in Step 2 are temporary files you create and delete; the
working tree must be clean at the end (`git status --porcelain` shows nothing
you added). Never edit a test or a config to "fix" a finding.

## Step 0 — Scope and conventions

- Default scope: every test directory in the repo. Narrow it if the user
  passed a path. Record the scope and the commit SHA in the report.
- Read the project's testing conventions: `CLAUDE.md` testing sections,
  `.claude/rules/testing.md`, ADRs about tests, mocks or isolation. A finding
  that contradicts a deliberate, documented project decision is not a finding;
  list it under "Deliberate deviations" instead.
- Read the previous audit if one exists (ask the user, or search the repo's
  docs and Issues), so findings can be marked new, fixed or still open.

## Step 1 — Inventory the harnesses

List each harness, where it is wired, and what it claims to enforce:

| Harness | Heuristic | Look for |
|---------|-----------|----------|
| Network / socket guard for unit tests | T16 | pytest-socket, custom guards, MSW `onUnhandledRequest: 'error'` |
| Console-output guard | T27 | fail-on-console setups, custom `setup` spies |
| Random order / parallel execution | T17 | pytest-randomly, pytest-xdist, Vitest `sequence.shuffle`, workers |
| Retry policy and its reporting | T21 | `--reruns`, Vitest/Playwright `retry`, whether retried passes are reported |
| Per-test state reset | T20 | DB rollback/truncate, env and settings isolation, `restoreMocks`, storage clearing |
| Coverage, and whether unit and integration are merged | T33 | coverage config, CI combine steps |
| Mutation testing / CRAP | T34–T35 | mutmut, Stryker, CRAP scripts, report-only vs gate |
| Skip / xfail policy | T32 | `xfail_strict`, skip markers, `.skip`, `.todo` |

A missing harness is a finding at the severity of the heuristic it would
enforce.

## Step 2 — Prove each harness covers what it claims

A harness that exists but leaks is worse than a missing one, because it is
trusted. For each harness from Step 1, write a **temporary** probe test that
should trip it, run it, record the result, and delete it. Examples:

- Network guard: open a socket in the test body, in fixture setup, **in fixture
  teardown**, and inside a broad `try/except` or `pytest.raises(Exception)`.
- Console guard: an undeclared `console.warn`, a React state update outside
  `act()`, a query function resolving `undefined`, a jsdom "Not implemented".
- Order isolation: run the suite (or the suspect files) shuffled and in
  parallel; compare with a serial run.
- Retry reporting: a test that fails once then passes; check the report names
  it.
- Coverage merge: check a module only integration tests exercise reports its
  real coverage.

Each leak is a High finding against the harness, with the probe as evidence.

## Step 3 — Mechanical scan

Run the "Audit check" of each heuristic that marks itself mechanical in the
Index, adapted to the repo's languages. Prefer existing linters over greps:
Ruff `B017` and `PT011` for broad exception assertions, `PT` and `B` rules
generally, eslint-plugin-jest / vitest rules, tsDetect-style rules for tests
without assertions. Collect raw hits with file:line; do not classify yet.

Also collect suite metrics (T32, Info): test count per tier, wall-clock per
job, skip/xfail counts, retry counts from recent CI runs, flaky reruns if the
CI exposes them.

## Step 4 — Classify (agent)

Spawn one classify agent (general-purpose, Read and Bash) with the Step 3 hits
and Step 2 probe results:

```text
You are classifying test-suite audit findings.
Read in full first:
  $HOME/.claude/skills/write-tests/references/test-philosophy.md
and the project's testing conventions: <paths from Step 0>.

For EVERY hit, read the test and ~20 lines around it before classifying.
Never classify from the grep line alone.

For each hit return:
- file:line
- heuristic (T1-T39)
- severity from the philosophy file (High/Medium/Low/Info); escalate only
  where that heuristic's text says to (e.g. T4 with an assertion inside the
  branch)
- category: FINDING / DELIBERATE (documented project decision) / FALSE
  POSITIVE
- one-line evidence from what you read
- suggested fix in one sentence

Treat smell detectors as prompts: when unsure, Low, not High.
Never present a [B] or [S] source as a quote.
```

Wait for the agent before continuing.

## Step 5 — Verify the High findings

For every High finding, confirm it yourself: re-read the code, and where
possible demonstrate it (a temporary mutation that the test fails to catch for
T28, a shuffled run that reproduces the order dependency for T17). Downgrade
or drop anything you cannot confirm, and say so. Delete every temporary file.

## Step 6 — Report

Follow the audit template's structure. Lead with:

1. **Harness table:** each harness, present or missing, and the Step 2 probe
   result.
2. **Findings by severity,** each with heuristic, file:line, evidence and fix.
   Group repeated instances of one pattern into a single finding with a count
   and examples.
3. **Suite metrics** (Info).
4. **Deliberate deviations** and **false positives** dropped, briefly.
5. **Compared with the previous audit:** fixed, still open, new.
6. **Proposed Issues,** one per independent fix, in priority order. Do not file
   them unless the user asks.

Cite the heuristic number for every finding so a reader can look up the
reasoning in the philosophy file.
