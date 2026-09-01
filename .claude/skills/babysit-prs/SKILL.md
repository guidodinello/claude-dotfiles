---
name: babysit-prs
description: >
  Orchestrate every open PR in this repo toward merge: check the self-hosted
  CI runner is healthy, triage failed CI runs (flaky vs. real), resolve merge
  conflicts, get unreviewed PRs reviewed via a free opencode model in a herdr
  pane, dispatch address-pr-comments on reviewed PRs with findings, and enable
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

Mental model: **Claude Sonnet agents write/fix code, a free opencode model
(via herdr) reviews it.** You are the orchestrator tying both together with
`gh`, never the one hand-editing PR branches yourself except for trivial,
mechanical merge-conflict resolution you're confident about.

## Herdr caveat

Step 3 (getting a PR reviewed) needs a live, interactive herdr pane running
opencode. This only works when invoked from an active herdr-managed session
(`test "${HERDR_ENV:-}" = 1`). If that check fails, stop and tell the user —
don't fall back to a headless `opencode run` fanout. Free-tier opencode
models churn frequently and several have failed silently in headless mode in
the past — hanging, posting empty/thin reviews, or mislabeling PRs — so
treat a headless fanout as unreliable rather than a fallback (see Step 3).

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

## Step 3 — Get unreviewed PRs reviewed (via herdr + opencode)

A PR needs review if it has no `reviewed` or `ready-to-merge` label (or has
`pending-review`).

1. Split a sibling pane per PR needing review (don't reuse one pane for
   multiple sequential reviews if you can parallelize — each is a real
   background wait):

   ```bash
   herdr pane split --current --direction right --cwd "$PWD" --no-focus
   ```

   (or `--direction down` off an already-split pane — avoid stacking splits
   in the same direction until columns/rows get unusably thin).

2. Start an opencode agent in the new pane:

   ```bash
   herdr agent start <name> --kind opencode --pane <pane-id>
   ```

   Model choice is a judgment call each run — check `opencode models | grep
   -- '-free$'` for what's currently available; the free tier churns
   constantly (models get added, withdrawn, or lose their free badge without
   warning). Don't hardcode a model list in this skill; if you want a
   specific one, pass it via `-- -m <model>` on `agent start`. If you have no
   prior signal for what's currently reliable, just take the default model
   opencode starts with.

3. Prompt it:

   ```bash
   herdr agent prompt <name> "/code-review <PR URL>" --wait --timeout 120000
   ```

   Expect the wait to time out (multi-agent code review legitimately takes
   10–25 min) — that's not a failure, it just means the command moved to
   background. Poll with `herdr agent get <name>` until `agent_status` is
   `idle`, then `herdr agent read <name> --source recent-unwrapped --lines
   150` to see what it posted.

### Verify the label transition — do not trust it blindly

The `code-review` skill's contract is: it **only ever sets the `reviewed`
label**, swapping out `pending-review` if present. It never sets
`ready-to-merge` — that label is exclusively `address-pr-comments`'s to set,
and only after threads are actually addressed and replied to.

After a review session goes idle, check the actual label
(`gh pr view <n> --json labels`) against what it *should* be:

- If the model jumped straight to `ready-to-merge` **and there's an
  unresolved blocking finding in its own posted review**, that's a
  mislabel — a real failure mode observed from at least one free model.
  Correct it back: `gh pr edit <n> --remove-label "ready-to-merge"
  --add-label "reviewed"`. Do not proceed to auto-merge on the strength of a
  label alone; check for inline comments with `[blocking]` markers
  regardless of what's labeled.
- If it posted a thin, generic-sounding review (a short body, no inline
  comments, on a PR that plausibly has something to say) treat it with
  suspicion — re-read the diff yourself or spawn a second model as a check
  before trusting a "no issues found" verdict on anything non-trivial.

## Step 4 — Address review findings

If a PR is `reviewed` and the review has any `[blocking]` or non-blocking
inline comments still unaddressed, spawn a Sonnet `Agent`
(`isolation: "worktree"`) instructed to run the `address-pr-comments` skill
against that PR number. Give it the specific findings you already know about
(don't make it re-discover context you have), but tell it to fetch the live
threads itself rather than trust your summary blindly. Also have it merge in
the base branch first if Step 1/2 identified a pending fix that hasn't
landed on this branch yet.

`address-pr-comments` sets the `ready-to-merge` label itself once done — you
don't need to.

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

## Loop until clear

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
resolved and how, what review findings were addressed, and — if more than
one model reviewed PRs this run — a short note on which one's output you'd
trust more next time and why (review quality vs. label/process discipline
are separate axes; call out mislabeling explicitly, it's a different failure
mode from a bad review).

Close any herdr panes you opened for this run once their work is done,
unless the user wants them kept open.
