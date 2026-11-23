---
name: babysit-prs
description: 'Trigger: babysit the PRs, clear the PR queue, orchestrate the open PRs, get everything mergeable. Drives open PRs to merge: CI triage, conflicts, herdr /code-review, address-pr-comments, auto-merge. Needs herdr; not headless or cron.'
---

# Babysit PRs

Runs the full multi-PR merge pipeline for the current repo, end to end, one pass at
a time. This is an orchestration *procedure*, not a single tool call — expect
to spawn several `Agent` calls and a couple of herdr panes, and to loop back
after each merge because landing one PR can put another into conflict.

Mental model: **Claude Sonnet agents write/fix code, and a separate herdr
Sonnet (high effort) session running the full `/code-review` reviews it.**
You are the orchestrator tying both together with `gh`, never the one
hand-editing PR branches yourself except for trivial, mechanical
merge-conflict resolution you're confident about.

## Step −1 — Load the project profile

This skill carries no project policy. Everything that differs per project (base
branch, merge method, runner, daemon, flake signatures) lives in a per-project
profile. Where to find it, first match wins:

1. An explicit path argument.
2. `<root>/my-dev-things/babysit-prs/README.md` when `<root>/my-dev-things/`
   exists. `<root>` is `git rev-parse --show-toplevel` of the session cwd.
3. Otherwise ask the user for a path before creating anything.

Read the profile. It holds these fields:

- base branch
- merge method (`squash`, `merge` or `rebase`) and where it comes from (an ADR
  or the base branch's ruleset)
- whether auto-merge is allowed
- whether the base branch requires review-thread resolution
- runner kind (`self-hosted` or `hosted`) and, for a self-hosted one, its health
  command
- host daemon service the CI jobs depend on, if any
- known flake signatures (log text plus how to retry)
- append-prone docs (files several PRs append to, a conflict hint)
- runner-capacity policy (what to cancel while PRs are queued)

For every field a later step needs and the profile lacks, stop and ask the user
one question at a time. Never assume a value. After the user confirms, write
the answers into the profile (create the file and folder if missing) so the next
run does not ask again.

## Herdr caveat

Step 3 (getting a PR reviewed) needs a live, interactive herdr pane running a
Claude session. This only works when invoked from an active herdr-managed
session (`test "${HERDR_ENV:-}" = 1`). If that check fails, stop and tell the
user — don't fall back to a headless review fanout or a single-reviewer
`claude -p` pass. The reviewer must run the full multi-agent `/code-review`.

## Step 0 — Runner health check

Only when the profile says the runner is self-hosted and gives a health
command: run that command and confirm the runner is `online`. Otherwise skip
the health check (a hosted runner has nothing to check).

In either case, if queued/executing runs pile up with more than one live run
per PR, cancel the older ones (`gh run cancel <id>`) — keep only the latest run
per branch.

## Step 1 — Triage failed CI runs before retrying

For every open PR, check `gh pr checks <n>`. For each failed job, read its
log (`gh run view <run-id> --log-failed`) and classify before touching
anything:

- **Known transient/runner flake** — retry with `gh run rerun <run-id>
  --failed`. The recognized signatures are the profile's known flake
  signatures; a failure that matches none of them is not known-transient. If a
  signature points at a host daemon, *first check if this is transient or the
  daemon is actually down* (see below).
- **Real, persistent infra problem** — the failure also reproduces outside CI
  (for example the profile's host daemon service reports `inactive (dead)`, or
  the tool it provides fails when run by hand). This is not flaky and a retry
  will not help. **Ask the user before restarting a host-level daemon** (the
  profile's host daemon service) — it's a host-affecting action, not a
  repo-scoped one.
- **Real, non-transient failure with a fix available** — e.g. `pip-audit`
  failing on a freshly-published CVE against a *transitive* dependency
  pinned in a lockfile. Investigate whether it's fixable with a lockfile
  bump (`uv lock --upgrade-package <pkg>`) before assuming it needs a code
  change or should just be added to an ignore-list. If it's a fix that
  unblocks CI for every other open PR (like a lockfile-pinned CVE), treat it
  as **P0**: branch, fix, review, merge it first via Steps 2–5 below, *then*
  merge it into every other open PR's branch before continuing their triage
  (`git fetch origin && git merge origin/<base>`, resolve trivial
  conflicts, push) — their own CI won't go green until they have the fix.
- **Real code failure** — don't retry; treat like any other reviewable
  problem (an actual bug the PR introduced).

## Step 2 — Merge conflicts

For any PR with `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING`, spawn a
Sonnet `Agent` (subagent_type default, `isolation: "worktree"`) with:

- The PR number, branch name, and base branch.
- Instruction to fetch, merge (or rebase) the base branch in, resolve
  conflicts by reading both sides and preserving both intents (don't
  silently drop either side — the profile's append-prone docs in
  particular tend to get independently-appended-to by multiple PRs; keep
  both additions, ordered sensibly, rather than picking one side), run the
  relevant test suite, and push (normal push, or `--force-with-lease` only
  if a rebase was used and clearly flagged).
- Explicitly: do NOT merge or touch auto-merge — that's a later step.

**This can happen more than once per PR.** Every time another PR merges into
the base branch during this session, every other open PR's merge state can
flip from clean to `DIRTY`. Re-check `gh pr list --state open --json
number,mergeStateStatus` after each merge and re-run this step as needed —
don't treat "resolved once" as permanent.

If you need to `git merge` yourself for something this trivial and you're
confident about it (e.g. a pure lockfile-only fix propagating, or two
independently-appended doc paragraphs with no real logical overlap), doing it
directly is fine — reserve the Sonnet agent for conflicts that need judgment
about actual source changes. Either way, run the affected test suite before
pushing.

## Step 3 — Get unreviewed PRs reviewed (herdr Sonnet + `/code-review`)

A PR needs review if it has no `reviewed` or `ready-to-merge` label (or has
`pending-review`). Do not hand-type the spawn recipe: one script does it.

```bash
python3 -I <this skill's base directory>/scripts/spawn_reviewer.py <PR> \
  [-R <owner/repo>] [--context "<PR-specific context>"]
```

Run it with `run_in_background`, one per PR, and handle its exit when notified.
**Max 3 concurrent reviewers**: the script refuses a 4th, so start the next one
when one exits. The default brief already tells the reviewer to run the full
review even if `/code-review`'s eligibility check calls the PR docs-only or
trivial; pass `--context` only for PR-specific notes. `-R` and the
config dir default from the repo and `$CLAUDE_CONFIG_DIR`, so it works from any
repo. What it does, how it labels (`reviewed`, plus `ready-to-merge` only for a
clean review of the still-current head) and the exit codes are documented in
the script's docstring (`spawn_reviewer.py --help`); do not copy them here.

What you must act on:

- Labels are touched only after the review is posted, never before; do not
  swap them yourself while it runs.
- Exit `0`: done, workspace and worktree already removed.
- Exit `2`: refused (not in herdr, PR not open or a draft, 3 already running, or
  a `rev<PR>` workspace exists). Nothing was started.
- Exit `124` (no review in `--timeout`) or `1` (any other failure, including
  the PR closing mid-review): labels untouched and the `rev<PR>` workspace is
  **kept** and blocks a re-spawn. Read it with `herdr agent read rev<PR>
  --source recent-unwrapped --lines 150`, then `herdr workspace close <id>`; a
  leftover worktree is removed by the next run.
- Do not poll `herdr agent get` by hand and do not treat `idle` as finished.

`opencode-dual-review` (free opencode models) is deprecated and opt-in only,
and `scripts/reviewer_leaderboard.py` only matters for it. Do not use either on
the default path.

### Verify the label transition — do not trust it blindly

The `code-review` skill's contract is: it swaps out `pending-review` for
**`reviewed` when its review has any finding** (blocking or non-blocking), or
for **`reviewed` plus `ready-to-merge` only when the review has zero findings**
(the "No issues found" review). Otherwise `ready-to-merge` is
`address-pr-comments`'s to add, and only after threads are actually addressed
and replied to. The two labels coexist — `reviewed` is never removed once set.

`spawn_reviewer.py` already reconciles the labels from the posted review, so a
mislabel from the reviewer session is normally corrected before it exits. Still
check the actual label (`gh pr view <n> --json labels`) against what it *should*
be before auto-merge, and when a review was triggered some other way:

- If the model jumped straight to `ready-to-merge` **and there's an
  unresolved blocking finding in its own posted review**, that's a
  mislabel — a real failure mode observed from at least one free model.
  Correct it back: `gh pr edit <n> --remove-label "ready-to-merge"
  --add-label "reviewed"` (keeping or adding `reviewed`). Do not proceed to auto-merge on the strength of a
  label alone; check for inline comments with `[blocking]` markers
  regardless of what's labeled.
- If it set `ready-to-merge` but its posted review has **any** inline comment
  or listed finding (even non-blocking), correct it back to `reviewed` the
  same way — findings go through `address-pr-comments` first.
- If it posted a thin, generic-sounding review (a short body, no inline
  comments, on a PR that plausibly has something to say) treat it with
  suspicion — re-read the diff yourself or spawn a second model as a check
  before trusting a "no issues found" verdict on anything non-trivial. Since
  that verdict now sets `ready-to-merge` directly, remove `ready-to-merge`
  (keeping `reviewed`) while you double-check, so nothing auto-merges on the strength of it.

## Step 4 — Address review findings

If a PR is `reviewed` but not `ready-to-merge` and the review has any `[blocking]` or non-blocking
inline comments still unaddressed, spawn a Sonnet `Agent`
(`isolation: "worktree"`) instructed to run the `address-pr-comments` skill
against that PR number. Give it the specific findings you already know about
(don't make it re-discover context you have), but tell it to fetch the live
threads itself rather than trust your summary blindly. Also have it merge in
the base branch first if Step 1/2 identified a pending fix that hasn't
landed on this branch yet.

`address-pr-comments` adds the `ready-to-merge` label itself once done
(leaving `reviewed` in place) — you don't need to. A PR labeled `reviewed`
(and not `ready-to-merge`) with **no** comments to address
(e.g. labeled by an older version of `code-review`) is stuck, not pending:
run `address-pr-comments` on it anyway — its nothing-to-address path still
adds `ready-to-merge`.

In a repo without a `ready-to-merge` label, `address-pr-comments` skips the edit
and reports `skipped — repo has no ready-to-merge label`. That PR will never get
the label: don't re-dispatch it. If the report shows no thread left open, treat
the PR as `ready-to-merge` for Step 5. If the report says `label lookup failed`
instead, that is transient: dispatch it again next pass.

## Step 5 — Auto-merge

Once a PR is CLEAN (not DIRTY), CI is green, and it's genuinely
`ready-to-merge` (reviewed with no unresolved blocking findings, or reviewed
clean with nothing to address):

```bash
gh pr merge <n> --auto --<profile merge method>
```

Use the merge method from the profile (`--squash`, `--merge` or `--rebase`). If
the profile has none, ask the user; do not guess. If the profile says auto-merge
is not allowed, stop and tell the user instead of merging.
Never merge directly (`gh pr merge` without `--auto`) unless the user
explicitly asks for an immediate merge — auto-merge is the default because
it waits for required checks rather than racing them.

If `enablePullRequestAutoMerge` fails with `"Pull request is in unstable
status"`, that's transient (checks still settling) — just retry once CI
progresses, don't treat it as a real error.

### Resolve review threads — a reply is not enough

If the base branch's ruleset requires thread resolution (the profile says so,
or check `gh api repos/{owner}/{repo}/rules/branches/<base>`), a PR with green
CI and auto-merge enabled will sit `BLOCKED` indefinitely if **any** review
thread is unresolved, and replying to a thread does not resolve it. Whenever a finding is addressed or dismissed (including a
false positive you rebut), resolve the thread explicitly:

```bash
# list unresolved threads
gh api graphql -F owner='{owner}' -F name='{repo}' -f query='query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){pullRequest(number:$n){reviewThreads(first:50){nodes{id isResolved comments(first:1){nodes{path body}}}}}}}' \
  -F n=<n> --jq '.data.repository.pullRequest.reviewThreads.nodes[]|select(.isResolved==false)'
# resolve one
gh api graphql -f query='mutation{resolveReviewThread(input:{threadId:"<PRRT_id>"}){thread{isResolved}}}'
```

If a PR is `BLOCKED` while every required check is green, check for
unresolved threads before anything else.

## Loop until clear

**Watch outcomes, not just merge state.** Never hand-write a `seq`/`sleep`
poll loop (they miss idle workers, are not re-armed, and read "no checks yet"
as a failure). Use the durable watcher, `scripts/watch.py` in this skill's
base directory (stdlib Python, drives `gh` and `herdr`). It covers every open
PR and the reviewer agents in one process, prints one line per event, and keeps
watching until every PR reaches a `--until` condition or the timeout:

```bash
python3 -I <this skill's base directory>/scripts/watch.py -R <owner/repo> \
  --pr <n> --pr <m> --agent <reviewer-name> \
  --until merged,closed,check-failed,dirty --timeout 90 --interval 30 \
  --state <durable-dir>/watch-<run>.json --exit-on-first-event
```

Run it with `run_in_background`; its exit notifies you. A PR is done only when
it is merged or closed (`--until` never changes that); every other `--until`
condition just wakes a `--exit-on-first-event` run, and the PR stays watched.
With that flag it exits 0 after the first event (a failed check, a new review, a
conflict, an agent going idle). **Exit 0 alone does not mean finished in that
mode: read the lines**, and only `ALL DONE` means every PR is merged or closed.
Handle the event, then start the same command again: `--state` makes the restart
diff against the last snapshot, so nothing that happened in between is lost and
an already-reported failure is not reported again. Without the flag it keeps
running, prints every event, and exits 0 only on `ALL DONE`. Other exit codes:
124 timeout; 3 `gh` or `herdr` missing; 4 `gh` not authenticated; 5 the same
target failed 5 polls in a row (wrong `--pr` or `-R`); 6 an `--agent` name
matched nothing. Codes 3-6 print a `FATAL` line, so do not treat them as a
normal timeout. Conditions: `merged closed review comment label label:NAME
check-failed dirty push`. Keep the state file somewhere durable, not the
scratchpad.

Rules it follows, so do not re-implement them: "no checks reported yet",
queued, in progress and cancelled runs are `pending`, never failure; an
`UNKNOWN` merge state keeps the last known value; an agent going `idle` is an
event, not completion. A reviewer that is idle can still be waiting on its own
sub-agents, so confirm completion from the PR (`--until review` or
`label:reviewed`), not from the pane. To stop a background watcher use
`--pidfile <file>` and `kill "$(cat <file>)"`, never `pkill -f`.

If it times out with nothing merged, go through the `BLOCKED` diagnosis above
rather than just waiting again.

**Keep runner capacity on PRs.** Only when the profile says the runner is
self-hosted and capacity-limited: it only has a few job slots. While PRs are
still queued, cancel every in-flight `CI` run on `<base>` (each intermediate
merge triggers one), and cancel any PR run whose `headSha` is no longer the PR's
head. Let only the `<base>` run triggered by the *last* merge complete, and
confirm it passes before wrapping up. The profile's runner-capacity policy
overrides this default.

After every merge, re-run `gh pr list --state open` — a merge can conflict
or re-trigger CI on the remaining PRs (Step 2's re-check applies here too).
Keep cycling Steps 1–5 across the remaining open PRs until the list is empty
or everything left is genuinely blocked on something only the user can
decide (e.g. a host-level fix, or a review finding you're not confident
overriding).

## Wrap-up

When the queue is clear (or as clear as it's going to get this pass), give
the user a concise summary: what merged, what infra issues were found and
how (runner health, CI flake vs. real failures), what conflicts were
resolved and how, what review findings were addressed, and any reviewer
session that mislabeled a PR or timed out (call mislabeling out explicitly,
it's a different failure mode from a bad review).

Close any herdr panes you opened for this run once their work is done,
unless the user wants them kept open.
