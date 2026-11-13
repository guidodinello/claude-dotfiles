---
name: sandbox-diff
description: "Trigger: run the harness, develop vs PR on sandbox data, verify a PR against the vendor sandbox, regression check before merge, simulate time for a scheduled job. Run base and PR code on the same sandbox data, safely; report only what ran."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.1"
---

## Activation Contract

Load before verifying a backend PR (open or merged) that touches a third-party vendor integration by running real code against the vendor's sandbox: base vs PR on the same data, a regression check before review, merge or release, or a scheduled job whose timing must be simulated. Also load when writing or extending a harness script.

Not for synthetic-data migration checks (`release-sim`) or for finding out what the vendor itself does (a vendor-behavior investigation). Writing tests stays with `write-tests`; this skill runs a diff-scoped mutation check on them.

The method lives here; everything project-specific lives in a per-project docs folder. Never put project, vendor, client or person names in this skill.

## Hard Rules

- **Base and PR are SHAs**, resolved at the start, quoted in the scenario, and checked out for every run. Never a branch or a squashed PR's head ref (method §0).
- **No path to a real person.** List every path from the flow to an email, SMS, push or vendor-sent message and make each impossible in every process that runs the code. If one cannot be, stop.
- **Writes only on the user's own allowlisted test accounts**, never a teammate's, through a scoped script that hard-codes the target and refuses a non-sandbox host. Log every write as it happens.
- **Claim only what ran.** Every cell comes from a run's output, using the cell vocabulary in method §8. Never fill a cell by inference.
- **Leave no trace.** Revert temporary code and config (`git status` clean) and restore changed local rows, or say they were left changed. Never start the app's scheduler.
- **Drafts only.** The user approves the PR comment before it is posted.

## Decision Gates

| Condition | Action |
|---|---|
| Docs folder missing | Bootstrap it from the template, show it, wait for confirmation |
| Docs folder exists in another shape | Use it as is; map each profile field to where it lives; do not restructure |
| Question is what each version selects or decides | **Decision-only**: block every vendor write, read decisions from attempted calls; simulate the response when the unit has no catch (method §2) |
| The written effect itself is the question | Real writes, PR first, base second; method §4 |
| Recent write-log entries on the same account show a check in progress | Block writes, or use another account |
| A worker or second process also runs the code | Run the unit in one stubbed process, do not start the worker |
| A deployed environment sweeps the same sandbox | Record its effects; do not fight them |
| Behavior depends on elapsed time | Move local dates, run the job directly |
| Change writes a table or documents an operator procedure | List every reader; run exactly the documented path |

## Execution Steps

1. Locate the docs folder: an explicit path, else `<root>/my-dev-things/harness/<topic>/`, else ask. Read it, the write log, and any scenario for the same PR (its base may differ).
2. State the question and the cases, each with the code line that predicts base and PR.
3. Safety gate, local prep, runs, recording, per [references/method.md](references/method.md).
4. Mutation check on the changed lines under the question (method §9).
5. Write the scenario and the PR comment draft from [references/docs-template.md](references/docs-template.md).

## Output Contract

Reply in the conversation language: scenario path, base and PR SHAs, the table, side effects and write-log entries (or `none, writes blocked`), not covered, local DB and `git status` state, and the PR comment draft for approval (optional for a merged PR).

## References

- [references/method.md](references/method.md): the full procedure.
- [references/docs-template.md](references/docs-template.md): profile, scenario, write-log entry, PR comment.
- [references/research.md](references/research.md): sources and what each changed.
- [examples/scoped-write.mjs](examples/scoped-write.mjs), [examples/capture-runner.ts](examples/capture-runner.ts): skeletons.
