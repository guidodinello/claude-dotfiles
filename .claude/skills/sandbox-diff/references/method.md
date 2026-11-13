# Method

A differential (back-to-back) run: the base branch and the PR on the same vendor-sandbox data, each result read from a real run. The base run characterizes what the system does today; the PR run shows what changes. Every difference is either the PR's intent or a regression, and the table says which.

```text
vendor sandbox (shared, writes often permanent)
   ▲ reads/writes through the app's vendor client
   │
local stack of the PR worktree ── local DB (yours, resettable)
   │ runs
   ├── PR code: the real job/command
   └── base code: the base version of the changed unit, same DB, same data
```

## 0. Frame the question

- List the cases. For each, write the expected outcome **for base and for PR** with the code line that predicts it (`file:line`). The base expectation comes from reading base, not from the ticket.
- Prefer data the sandbox already has. Read-only scripts first; create data only for cases nothing existing covers.
- When real sandbox payloads are free to read, check the change's assumptions against them, not only against synthetic seeds: a seed encodes the same assumptions as the code.

## 1. Safety gate (before anything that can write or send)

**Find every path to a real person.** Trace from the flow's entry to every outbound effect: email, SMS, push, webhook, and vendor endpoints that send on your behalf (a "create link" or "invite" call with a send flag, a message-thread create). Use `backward-trace` on the vendor client: list its methods, then every caller reachable from the flow. Write the list with `file:line` into the scenario.

**Neutralize each one, in the worktree only, never in a committed file:**

| Technique | Use when | Limit |
|---|---|---|
| Capture runner: replace the vendor client's methods in-process; allowlisted reads stay real, listed sends are captured and printed, everything else throws | The flow runs in one process you start | Covers only that process |
| Dead host: point the vendor base URL at `http://127.0.0.1:9` for the runner | Second layer under the capture runner | Env set on the runner does not reach other containers |
| Vendor test credentials or magic values (some SMS/payment vendors never deliver with them) | The vendor offers them | Not every vendor has them |
| Local mail/SMS sink (SMTP catcher) | The app sends through its own SMTP or provider client | Useless when the vendor sends |
| Network deny in tests (`nock.disableNetConnect`, `pytest-socket`) | Unit/integration tests | Not for sandbox runs |

Prefer **deny by default**: an allowlist of read methods, everything else throws. Enumerating the send methods fails open when someone adds a new one.

**Cover every process that runs the code.** A command that enqueues a job is executed by the queue worker, with unstubbed services and its own env. A scheduler container runs every sweep unattended. Either stop those services and invoke the unit in the stubbed process, or prove they cannot reach a send path. Check `docker ps` before and after.

**Self-test the stub.** Before the real run, call one unlisted method through the runner and confirm it throws. A stub that walks only the direct prototype misses inherited methods.

**If a path cannot be made impossible, stop** and tell the user. Do not run "carefully".

**Scoped write scripts** (one per resource kind, see `examples/scoped-write.mjs`):

- Hard-code the allowlisted test account and resource ids; refuse any other.
- Print the API host first; refuse anything but the sandbox host.
- Re-read what was created and check it is the scoped one before writing more.
- Keep credentials inside the process; print ids, statuses and scores only.
- One mode per action (`create`, `flag`, `show`); read-only modes are separate.
- Tag what you create (an external id or a name prefix) when the vendor allows it, so later reads can tell harness data from everything else.

## 2. Local state prep

- **Fresh enough schema.** Tables exist and match the branch: re-run migrations when the local schema is stale (a dropped column still `NOT NULL` breaks inserts). Restart app processes that booted before the tables existed.
- **Old data stays old.** Mark pre-existing vendor records as already processed in the local DB, so a local sweep acts only on the records the case needs. Local DB edits only.
- **Narrow the population.** Seed only the test accounts the case needs; jobs that load "every local record" then touch no one else.
- **Temporary code or config** (a mapping the branch lacks, a low threshold): apply as an uncommitted change in the worktree, list it in the scenario, revert, `git status` clean.
- Stack isolation and keeping the scheduler off are `worktree-bootstrap`'s job.

## 3. Run order and noise

The second run's input includes the first run's writes. Pick the order per case:

| Case | Order |
|---|---|
| Read-only, or writes only local state you can reset | Any order; reset the local DB between runs if both must see the same input |
| Writes to the vendor that the other version would also act on | **PR first, base second**, so base does not re-create what PR already wrote (vendor data often cannot be deleted) |
| Base must see a record PR already consumed | Accept it and write `not seen: consumed by the PR run`, or reset only the local marker and record that base re-wrote to the vendor |

Restoring a local DB snapshot gives both versions identical input, but the second version then writes to the vendor again. Decide per case and say which in the scenario.

**Run the base version.** Two options:

- A second worktree at the base SHA on the same DB (clean, heavier).
- Swap only the changed unit: copy the base file into the running container outside mounted paths, build it with the PR's dependencies, call it once. Cheaper; only that file is base, its imports are the PR's. Say so in the table header.

**Noise baseline.** Re-run the same version once more on the same data. Anything that changes between two runs of the same code (ids, timestamps, order, a deployed environment's sweep) is noise, not a PR difference. Normalize ids and timestamps before comparing.

## 4. Shared-environment side effects

A deployed environment can sweep the same sandbox on its own schedule and act on the records you created (duplicates, a second split, a status change). Before the first write, find its job's cron cadence in the code and whether it points at the same sandbox. Then record its effects as side effects in the scenario, with times; do not pause, race or undo it. When waiting for its result, wait for the next tick, not a fixed time.

## 5. Time simulation for scheduled jobs

- Run the job's unit directly instead of waiting for the scheduler; note that the real cadence was not exercised.
- Move time in data, not in the clock: set local dates relative to now (`completed_at = now - 61 days`), or feed synthetic vendor-dated inputs through the capture runner (an appointment at day + N).
- If the code reads an injectable clock, inject it in unit tests instead. Faking the process clock (libfaketime) also moves auth-token expiry and TLS validity, so sandbox calls fail for reasons unrelated to the change.
- Walk the boundaries: the day before, the day of, the day after, and a second run on the same day (sent once, not twice).

## 6. Recording

- **Write log (per project, append-only):** one entry per sandbox write, written right after it: date, script and mode, account, created or changed ids, why. Vendor data often cannot be deleted; the log is how the next run knows what exists.
- **Scenario file per run:** question, safety (paths found, how each was neutralized), setup (SHAs, local prep, temporary changes reverted), the expected-vs-observed table with `file:line` citations, observations that are not regressions, side effects, not covered.
- **PR comment:** a draft built from the scenario table. The user approves the exact text before it is posted.

## 7. Claim only what ran

- Each observed cell quotes or summarizes output from a run in this session or a cited earlier scenario. Before writing the draft, match every cell to its run.
- Cells use: an observed value; `not run`; `not seen: consumed by the <x> run`; `unit-tested only (<spec file>)`; `observed live on <env>, not run locally`.
- A case whose run failed for an unrelated reason is `not run`, with the reason.

## 8. Mutation check

On the lines the PR changed only, reintroduce the old behavior (revert the fix line, flip the guard), run the new tests, confirm they fail for the expected reason, restore, `git status` clean. A test that still passes does not cover the fix. Full mutation tools are overkill for this; the diff-scoped check is the point.

## 9. Readers and the documented path

- **Every reader of every table the change writes**, in code or in documented SQL: grep the entity and the table name across apps, jobs and crons, and state the effect on each. A reset of a row can also move another feature's cycle.
- **Operator procedures** (docs, SQL, commands): the test or harness must run exactly the documented path, not an equivalent one. A delete and a reset reach different code.
