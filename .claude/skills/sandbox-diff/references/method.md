# Method

A differential (back-to-back) run: the base and the PR, each pinned to a SHA, on the same vendor-sandbox data, each result read from a real run. The base run characterizes what the system does today; the PR run shows what changes. Every difference is either the PR's intent or a regression, and the table says which.

```text
vendor sandbox (shared, writes often permanent)
   ▲ reads/writes through the app's vendor client
   │
local stack of the PR worktree ── local DB (yours, resettable)
   │ runs
   ├── PR code: the real job/command
   └── base code: the base version of the changed unit, same DB, same data
```

## 0. Pin the refs and frame the question

- **Resolve base and PR to SHAs** (`git rev-parse`) and write both in the scenario header.
  - Open PR: base = `git merge-base <target> <pr head>`; PR = the head SHA.
  - Merged PR: PR = the merge commit; base = its first parent (`<merge>^1`).
  - Squash merge: `git cat-file -p <merge>` shows one `parent` line (`<merge>^2` fails). PR = the squash commit; base = its parent. The PR's head ref (`headRefOid`) is **not** the PR SHA: it may have branched before other merged work, so code at the head lacks changes the squash commit has.
  - **Every run, not only the mutation check, comes from the PR SHA.** Check the worktree's `HEAD`; if it differs, `git switch --detach <pr sha>` and switch back at the end.
  - Check every run helper honours the SHA. A helper that runs `git show <target branch>:<file>` runs PR code once the PR is merged, and the table then reports "no difference".
- **Reuse earlier work carefully.** If a scenario for the same PR exists, read it and cross-link it; write a new file for a new run instead of editing its table. Its base expectations hold only if its base SHA equals yours.
- **Separate versions stay separate.** "PR as merged" and "PR plus a temporary change" (a later data fix applied locally so the case is reachable at all) are different rows or columns, never one. The table must not claim the merged code did what only the patched code did.
- List the cases, before any run, in the scenario's Expected section. For each, write the expected outcome **for base and for PR** with the code line that predicts it (`file:line`). The base expectation comes from reading base at its SHA, not from the ticket or an earlier scenario.
- Prefer data the sandbox already has. Read-only scripts first; create data only for cases nothing existing covers.
- When a case depends on how a person acts in the vendor's UI, shape the data through UI automation (Playwright) on the real portal: some vendors enforce rules only in their UI, and the API can accept states the UI refuses. Label any API-shaped state the UI cannot produce, or the table tests an impossible state.
- When real sandbox payloads are free to read, check the change's assumptions against them, not only against synthetic seeds: a seed encodes the same assumptions as the code.

## 1. Safety gate (before anything that can write or send)

**Find every path to a real person.** Trace from the flow's entry to every outbound effect: email, SMS, push, webhook, and vendor endpoints that send on your behalf (a "create link" or "invite" call with a send flag, a message-thread create). When the unit is one file with no dispatch (it does not enqueue, emit events or call other actions), grepping its vendor-client calls at both SHAs is exhaustive. Otherwise use `backward-trace` on the vendor client: list its methods, then every caller reachable from the flow. Write the list with `file:line` into the scenario.

**Neutralize each one, in the worktree only, never in a committed file:**

| Technique | Use when | Limit |
|---|---|---|
| Capture runner: replace the vendor client's methods in-process; allowlisted reads stay real, listed sends are captured and printed, everything else throws. It prints the API host first and refuses anything but the sandbox, like a write script, because its reads are real | The flow runs in one process you start | Covers only that process |
| Dead host: point the vendor base URL at `http://127.0.0.1:9` for the runner | Second layer under the capture runner | Env set on the runner does not reach other containers |
| Vendor test credentials or magic values (some SMS/payment vendors never deliver with them) | The vendor offers them | Not every vendor has them |
| Local mail/SMS sink (SMTP catcher) | The app sends through its own SMTP or provider client | Useless when the vendor sends |
| Network deny in tests (`nock.disableNetConnect`, `pytest-socket`) | Unit/integration tests | Not for sandbox runs |

Prefer **deny by default**: an allowlist of read methods, everything else throws. Enumerating the send methods fails open when someone adds a new one.

**Cover every process that runs the code.** A command that enqueues a job is executed by the queue worker, with unstubbed services and its own env. A scheduler container runs every sweep unattended. Simplest: call the unit directly in one stubbed process and do not start the worker; the job wrapper is then `not run`. Also check what the app process itself runs on boot (migrations, queue consumers, in-process crons) before starting it: an app container that consumes jobs is a worker. Otherwise prove the other processes cannot reach a send path. Check `docker ps` before and after.

**Self-test the stub.** Before the real run, call one unlisted method through the runner and confirm it throws.

**Audit a runner before reusing it**, at the SHA you will run:

- It walks the whole prototype chain and own function properties; a stub over the direct prototype misses inherited methods.
- Every name in its read and internal allowlists exists on the client at that SHA, and so does its self-test target (a missing target throws a `TypeError`, not the harness error).
- Its claims about the unit hold at that SHA (for example "the unit catches errors per item"): read the unit, not the runner's header.
- It prints and checks the host.

**If a path cannot be made impossible, stop** and tell the user. Do not run "carefully".

**Script language follows where the code runs.** Scripts that run outside the app (scoped writes, read-only probes, run helpers) use Python stdlib, run with `python3 -I`, or shell. Anything that runs inside the app's process (a capture runner, a base-version runner) uses the project's language, because it loads the app's own client.

**Scoped write scripts** (one per resource kind, see `examples/scoped-write.py`):

- Hard-code the allowlisted test account and resource ids; refuse any other.
- Print the API host first; refuse anything but the sandbox host.
- Re-read what was created and check it is the scoped one before writing more.
- Keep credentials inside the process; print ids, statuses and scores only.
- One mode per action (`create`, `flag`, `show`); read-only modes are separate.
- Tag what you create (an external id or a name prefix) when the vendor allows it, so later reads can tell harness data from everything else.

## 2. Write mode: decision-only or real writes

| Question | Mode |
|---|---|
| Which records each version selects, skips or would write (a decision) | **Decision-only** (default) |
| The written payload or its downstream effect is what is under test | Real writes on the test account |

**Decision-only:** block every vendor write in the runner, for both versions, the same way sends are blocked. Each blocked call is recorded (method, target id, a summary of the payload, such as a tag or external id) and then throws. Read each version's decision from its attempted calls and its logs. Zero sandbox writes, no write-log entries, no permanent duplicates, both versions see identical input, and order does not matter. The unit's own error handling may catch the throw; that is fine as long as the attempt was recorded. Cells read `attempted, blocked: <call> <id>`.

Throw or simulate:

| The unit at that SHA | Blocked write |
|---|---|
| Catches errors per item, or the decision is complete at the first write | **Throw** (default) |
| Has no catch around the write, and the decision continues past it (later writes, routing of the rest) | **Simulate**: return a response built from real reads (the destination's real definition, the record as it would exist) so the unit continues; the call still never reaches the vendor |

Read the unit at both SHAs to choose; the choice can differ per version. A simulated response is harness-built: say how it was built in the scenario, and label those cells `simulated: <call> <target>`. A difference that appears only after a simulated response depends on the simulation being faithful.

**Real writes:** only when the effect is the question. Before the first write:

- Read the write log's latest entries for the same test account. If another check is in progress that depends on the account's current state (a derived score, a pending sync), block writes or use another account.
- Find what derives state from the records you will write, both locally and in deployed environments on the same sandbox (§5). Your write can change what they show.

## 3. Local state prep

- **Fresh enough schema.** Tables exist and match the branch: re-run migrations when the local schema is stale (a dropped column still `NOT NULL` breaks inserts). Restart app processes that booted before the tables existed.
- **Old data stays old.** Mark pre-existing vendor records as already processed in the local DB, so a local sweep acts only on the records the case needs. Local DB edits only.
- **Isolate cases when a version aborts.** If a version can abort the sweep on one record, run each case on its own: one unprocessed record per run, everything else marked processed.
- **Snapshot before, restore after.** Other scenarios share the local DB. Save the rows you change (`COPY ... TO`, or a `SELECT` into a scratch table) and restore them at the end, or state in the scenario that the local DB was left changed and how.
- **Narrow the population.** Seed only the test accounts the case needs; jobs that load "every local record" then touch no one else.
- **Temporary code or config** (a mapping the branch lacks, a low threshold): apply as an uncommitted change in the worktree, list it in the scenario, revert, `git status` clean.
- Stack isolation and keeping the scheduler off are `worktree-bootstrap`'s job.

## 4. Run order and noise

The second run's input includes the first run's writes. Pick the order per case:

| Case | Order |
|---|---|
| Read-only, or writes only local state you can reset | Any order; reset the local DB between runs if both must see the same input |
| Real writes to the vendor that the other version would also act on | **PR first, base second**, so base does not re-create what PR already wrote (vendor data often cannot be deleted) |
| Base must see a record PR already consumed | Accept it and write `not seen: consumed by the PR run`, or reset only the local marker and record that base re-wrote to the vendor |

Restoring a local DB snapshot gives both versions identical input, but the second version then writes to the vendor again. Decide per case and say which in the scenario.

**Run the base version.** Two options:

- A second worktree at the base SHA on the same DB (clean, heavier).
- Swap only the changed unit (record the faithfulness check in the scenario's Setup): copy the base file (`git show <base sha>:<path>`) into the running container outside mounted paths, build it with the PR's dependencies, call it once. Cheaper; only that file is base, its imports are the PR's. Faithful only if the base file imports none of the PR's other changed source files (`git diff --name-only <base>..<pr>`), or the change there is additive.

**Noise baseline.** Re-run the same version once more on the same data. Anything that changes between two runs of the same code (ids, timestamps, order, a deployed environment's sweep) is noise, not a PR difference. Normalize ids and timestamps before comparing.

## 5. Shared-environment side effects

A deployed environment can sweep the same sandbox on its own schedule and act on the records you created (duplicates, a second split, a status change). Before the first write, find its job's cron cadence in the code and whether it points at the same sandbox. Then record its effects as side effects in the scenario, with times; do not pause, race or undo it. When waiting for its result, wait for the next tick, not a fixed time.

The other direction matters as much: your writes change the state a deployed environment derives (a newer record replaces the one a score or status is computed from), and another in-progress check may depend on it. That is the write-log gate in §2.

## 6. Time simulation for scheduled jobs

- Run the job's unit directly instead of waiting for the scheduler; note that the real cadence was not exercised.
- Move time in data, not in the clock: set local dates relative to now (`completed_at = now - 61 days`), or feed synthetic vendor-dated inputs through the capture runner (an appointment at day + N).
- If the code reads an injectable clock, inject it in unit tests instead. Faking the process clock (libfaketime) also moves auth-token expiry and TLS validity, so sandbox calls fail for reasons unrelated to the change.
- Walk the boundaries: the day before, the day of, the day after, and a second run on the same day (sent once, not twice).

## 7. Recording

- **Write log (per project, append-only):** one entry per sandbox write, written right after it: date, script and mode, account, created or changed ids, why. Vendor data often cannot be deleted; the log is how the next run knows what exists.
- **Scenario file per run:** question, expected (before the run), safety (paths found, how each was neutralized), setup (SHAs, local prep, temporary changes reverted), the expected-vs-observed table with `file:line` citations, observations that are not regressions, side effects, not covered.
- **PR comment:** a draft built from the scenario table, kept at the end of the scenario file. The user approves the exact text before it is posted. For a merged PR, the comment is optional: ask whether to post it for the record, or, when you cannot ask (a delegated run), mark it `not posted; optional`.

## 8. Claim only what ran

- Each observed cell quotes or summarizes output from a run in this session or a cited earlier scenario. Before writing the draft, match every cell to its run.
- Cells use: an observed value; `attempted, blocked: <call> <id>` (decision-only); `simulated: <call> <target>` (decision-only, harness-built response); `not run`; `not seen: consumed by the <x> run`; `unit-tested only (<spec file>)`; `observed live on <env>, not run locally`.
- A case whose run failed for an unrelated reason is `not run`, with the reason.

## 9. Mutation check

1. Run from the exact PR SHA. If the worktree's branch differs, `git switch --detach <pr sha>` and switch back at the end.
2. Run the new tests on the unmutated code and confirm they pass, in this session.
3. For each changed line under the question, reintroduce the old behavior (revert the fix line, flip the guard), run the tests, confirm they fail for the expected reason, restore with `git checkout -- <file>`.
4. `git status` clean. List which changed lines were mutated and which were not (`not mutation-checked`), so the report does not imply full coverage.

Config and data lines (ids, mapping tables, thresholds) usually cannot be mutation-checked offline: whether an id is right depends on the vendor's live state. Say so, and point to the sandbox run (or a read of the vendor's published definition) as their check. This is often the strongest reason to run the harness at all.

A test that still passes does not cover the fix. Full mutation tools are overkill for this; the diff-scoped check is the point.

## 10. Readers and the documented path

- **Every reader of every table the change writes**, in code or in documented SQL: grep the entity and the table name across apps, jobs and crons, and state the effect on each. Say whether readers outside the code (BI dashboards, documented SQL) were checked. A reader's effect may be cited from an earlier scenario when the SHA and the reader's code are the same: write `observed in <scenario>, not re-run`. A reset of a row can also move another feature's cycle.
- **Operator procedures** (docs, SQL, commands): the test or harness must run exactly the documented path, not an equivalent one. A delete and a reset reach different code.
