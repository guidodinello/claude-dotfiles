---
name: sandbox-diff
description: "Trigger: run the harness, develop vs PR on sandbox data, verify a PR against the vendor sandbox, regression check before merge, simulate time for a scheduled job. Run base and PR code on the same sandbox data, safely; report only what ran."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load before verifying a backend PR that touches a third-party vendor integration by running real code against the vendor's sandbox: base branch vs PR on the same data, a regression check before review, merge or release, or a scheduled job whose timing must be simulated. Also load when writing or extending a harness script.

Not for synthetic-data migration and backfill checks (`release-sim`), and not for finding out what the vendor itself does (a vendor-behavior investigation; feed its findings back there). Unit and mutation tests stay with `write-tests`.

The method lives here. Everything project-specific (stack commands, allowlisted test accounts, write-log path, scoped scripts, scenarios) lives in a per-project docs folder. Never put project, vendor, client or person names in this skill.

## Hard Rules

- **No path to a real person.** Before any run, list every path from the flow to an email, SMS, push or vendor-sent message (including the vendor's own API sending on your behalf) and make each impossible, in every process that runs the code, not only the runner. If one cannot be made impossible, stop.
- **Writes only on allowlisted test accounts**, through a scoped script that hard-codes the target, refuses anything else, and prints the API host first and refuses a non-sandbox host. Every write goes in the append-only write log as it happens.
- **Claim only what ran.** Every result cell comes from an actual run, quoted from its output. A case not run says `not run`; unit-test coverage says `unit-tested only`. Never fill a cell by inference.
- **Leave no trace in the repo.** Temporary code, data and config changes are uncommitted and reverted; `git status` is clean at the end. Never start the app's scheduler.
- **Drafts only.** The PR comment is a draft the user approves before it is posted.

## Decision Gates

| Condition | Action |
|---|---|
| Docs folder missing | Bootstrap it from the template, show it, wait for confirmation |
| The flow writes to the vendor | PR first, base second on the same DB; see run order in the method |
| Only reads, or writes local only | Run in any order; repeat freely |
| A send path can only be stubbed in-process, but a worker or second container also runs the code | Stop that service, or run the code in the stubbed process only |
| A deployed environment sweeps the same sandbox | Record its duplicates as side effects; do not fight them |
| Behavior depends on elapsed time | Move local dates and run the job directly; do not fake the process clock |
| Change writes to a table, or documents an operator procedure | List every reader of the table (`backward-trace`); run exactly the documented path |

## Docs Folder Location

First match wins: an explicit path; `<root>/my-dev-things/harness/<topic>/` when `<root>/my-dev-things/` exists (`<root>` is the session cwd's git toplevel, or the cwd for a multi-repo workspace); otherwise ask. The write log is per project, not per topic; the profile names its path.

## Execution Steps

1. Read the docs folder and the write log. State the question and the cases, each with the code line that predicts its outcome.
2. Safety gate, then local state prep, then runs, per [references/method.md](references/method.md).
3. Mutation check: reintroduce the old behavior on the changed lines, confirm the new tests fail, restore.
4. Write `scenarios/<change>.md` and the PR comment draft from [references/docs-template.md](references/docs-template.md).

## Output Contract

Reply in the conversation language: scenario path, the expected-vs-observed table, side effects and write-log entries, what was not covered, `git status` result, and the PR comment draft for approval.

## References

- [references/method.md](references/method.md): the full procedure.
- [references/docs-template.md](references/docs-template.md): profile, scenario, write-log entry, PR comment.
- [references/research.md](references/research.md): sources and what each changed.
- [examples/scoped-write.mjs](examples/scoped-write.mjs), [examples/capture-runner.ts](examples/capture-runner.ts): skeletons.
