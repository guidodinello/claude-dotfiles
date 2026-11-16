---
name: babysit-prs
description: >
  Orchestrate every open PR in this repo toward merge: check the self-hosted
  CI runner is healthy, triage failed CI runs (flaky vs. real), resolve merge
  conflicts, get unreviewed PRs reviewed by a herdr Sonnet session running the
  full /code-review (scripts/spawn_reviewer.py), dispatch address-pr-comments on reviewed PRs with findings, and enable
  auto-merge on anything clean. Use when the user asks to "babysit the PRs",
  "clear the PR queue", "orchestrate the open PRs", or "get everything
  mergeable" for this repo. Requires an interactive herdr session — do not use
  from a headless/cron context (see the Herdr caveat below).
---

# Babysit PRs

Runs the full multi-PR merge pipeline this repo uses, end to end, one pass at
a time. This is an orchestration *procedure*, not a single tool call — expect
to spawn several `Agent` calls and a couple of herdr panes, and to loop back
after each merge because landing one PR can put another into conflict.

Mental model: **Claude Sonnet agents write/fix code, and a separate herdr
Sonnet (medium effort) session running the full `/code-review` reviews it.**
You are the orchestrator tying both together with `gh`, never the one
hand-editing PR branches yourself except for trivial, mechanical
merge-conflict resolution you're confident about.

## Herdr caveat

Step 3 (getting a PR reviewed) needs a live, interactive herdr pane running a
Claude session. This only works when invoked from an active herdr-managed
session (`test "${HERDR_ENV:-}" = 1`). If that check fails, stop and tell the
user — don't fall back to a headless review fanout or a single-reviewer
`claude -p` pass. The reviewer must run the full multi-agent `/code-review`.

## Step 0 — Runner health check

```bash
uv run scripts/runner_ctl.py status
```

(Use `uv run`, not bare `python3` — the script has inline `uv` script
metadata for its deps like `psutil`; running it with plain `python3` fails
with `ModuleNotFoundError`.)

Confirm the runner is `online`. If queued/executing runs pile up with more
than one live run per PR, cancel the older ones (`gh run cancel <id>`) —
keep only the latest run per branch.

## Step 1 — Triage failed CI runs before retrying

For every open PR, check `gh pr checks <n>`. For each failed job, read its
log (`gh run view <run-id> --log-failed`) and classify before touching
anything:

- **Known transient/runner flake** — retry with `gh run rerun <run-id>
  --failed`. Recognized signatures so far:
  - Docker socket connection refused during "Initialize containers" —
    *but first check if this is transient or the daemon is actually down*
    (see below).
  - `gpg: signing failed: Inappropriate ioctl for device` mid-test-suite —
    a concurrent-job gpg-agent/tty race, unrelated to the code under test.
- **Real, persistent infra problem** — e.g. `docker version` also fails
  outside CI (`docker version --format '{{.Server.APIVersion}}'`) and
  `systemctl --user status docker-desktop` shows `inactive (dead)`. This is
  not flaky and a retry will not help. **Ask the user before restarting a
  host-level daemon** (`systemctl --user start docker-desktop` or similar) —
  it's a host-affecting action, not a repo-scoped one.
- **Real, non-transient failure with a fix available** — e.g. `pip-audit`
  failing on a freshly-published CVE against a *transitive* dependency
  pinned in a lockfile. Investigate whether it's fixable with a lockfile
  bump (`uv lock --upgrade-package <pkg>`) before assuming it needs a code
  change or should just be added to an ignore-list. If it's a fix that
  unblocks CI for every other open PR (like a lockfile-pinned CVE), treat it
  as **P0**: branch, fix, review, merge it first via Steps 2–5 below, *then*
  merge it into every other open PR's branch before continuing their triage
  (`git fetch origin && git merge origin/development`, resolve trivial
  conflicts, push) — their own CI won't go green until they have the fix.
- **Real code failure** — don't retry; treat like any other reviewable
  problem (an actual bug the PR introduced).

## Step 2 — Merge conflicts

For any PR with `mergeStateStatus: DIRTY` / `mergeable: CONFLICTING`, spawn a
Sonnet `Agent` (subagent_type default, `isolation: "worktree"`) with:

- The PR number, branch name, and base branch.
- Instruction to fetch, merge (or rebase) the base branch in, resolve
  conflicts by reading both sides and preserving both intents (don't
  silently drop either side — this repo's process/issue tracker docs in
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
It:

1. Refuses to start unless it is inside herdr, the PR is open, no `rev<PR>`
   workspace exists yet, and fewer than 3 reviewer workspaces (`rev<N>`) are
   running. **Max 3 concurrent reviewers**; start the next one when one exits.
2. Adds a detached worktree of the PR head branch, creates the herdr workspace
   `rev<PR>` with `CLAUDE_CONFIG_DIR` set, and starts Claude Sonnet (medium
   effort, auto permission mode) in it.
3. Sends the full `/code-review` brief (all sub-agents, no fallback, no polling
   with sleep). `--context` appends PR-specific facts, for example "This PR
   needs a full review; do not skip it as simple or docs-only" for a docs PR,
   because the skill's eligibility check may otherwise skip it.
4. Waits for the review to be **posted** (a new review starting with
   `### Code review`), not for the pane to go idle: a reviewer waiting on its
   own sub-agents is idle. It uses `watch.py` as a wake signal.
5. Lets the reviewer finish its own label swap, then reconciles the labels from
   the posted review: **clean** (`No issues found`, no inline comments) gives
   `reviewed` + `ready-to-merge`; anything else gives `reviewed` only and
   removes a `ready-to-merge` the reviewer set by mistake. Labels are never
   touched before the review exists.
6. Closes the workspace and removes the worktree (`--keep` skips this).

Defaults come from the repo and environment (`-R` from `origin`,
`--config-dir` from `$CLAUDE_CONFIG_DIR`, else `~/.claude`), so it works from
any repo. Exit codes: `0` done, `2` refused (not in herdr, PR not open, limit
or duplicate), `3` a tool is missing, `124` no review within `--timeout`
(default 45 min; labels untouched, workspace and worktree kept so you can read
the reviewer with `herdr agent read rev<PR> --source recent-unwrapped
--lines 150`). Do not poll `herdr agent get` by hand and do not treat `idle`
as finished.

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

## Step 5 — Auto-merge

Once a PR is CLEAN (not DIRTY), CI is green, and it's genuinely
`ready-to-merge` (reviewed with no unresolved blocking findings, or reviewed
clean with nothing to address):

```bash
gh pr merge <n> --auto --squash
```

Per this repo's ADR-027, feature → `development` is always squash-merged.
Never merge directly (`gh pr merge` without `--auto`) unless the user
explicitly asks for an immediate merge — auto-merge is the default because
it waits for required checks rather than racing them.

If `enablePullRequestAutoMerge` fails with `"Pull request is in unstable
status"`, that's transient (checks still settling) — just retry once CI
progresses, don't treat it as a real error.

### Resolve review threads — a reply is not enough

The `development` ruleset sets `required_review_thread_resolution: true`.
A PR with green CI and auto-merge enabled will sit `BLOCKED` indefinitely
if **any** review thread is unresolved, and replying to a thread does not
resolve it. Whenever a finding is addressed or dismissed (including a
false positive you rebut), resolve the thread explicitly:

```bash
# list unresolved threads
gh api graphql -f query='query($n:Int!){repository(owner:"guidodinello",name:"fitted"){pullRequest(number:$n){reviewThreads(first:50){nodes{id isResolved comments(first:1){nodes{path body}}}}}}}' \
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
python3 -I <home>/.claude/skills/babysit-prs/scripts/watch.py -R <owner/repo> \
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

**Keep runner capacity on PRs.** The self-hosted runner only has a couple
of job slots. While PRs are still queued, cancel every in-flight `CI` run
on `development` (each intermediate merge triggers one), and cancel any
PR run whose `headSha` is no longer the PR's head. Let only the
`development` run triggered by the *last* merge complete, and confirm it
passes before wrapping up.

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
