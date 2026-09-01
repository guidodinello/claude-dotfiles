---
name: address-pr-comments
description: >
  Address incoming PR review comments end-to-end: fetch all unresolved inline
  review threads AND PR review summaries, assess their validity, fix valid ones,
  commit and push, then reply to every thread (and each review summary) with the
  outcome. Use when a PR has received review feedback that needs to be triaged
  and responded to.
---

# Address PR Comments

Automates the full loop for responding to PR review comments: fetch → assess → fix → commit → reply.

## Invocation

```
/address-pr-comments [PR#] [--auto]
```

`PR#` is optional. Omit it to use the current branch's open PR.

`--auto` skips the Step 3 confirmation gate and proceeds directly to applying fixes. Use this flag in routines and automated contexts where no human is present to confirm. Without `--auto`, the skill stops at Step 3 and waits for explicit user approval.

## Step 0 — Resolve the PR

```bash
gh pr view [PR#] --json number,headRefName,baseRefName,url,state
gh repo view --json owner,name
```

- If no open PR is found, stop and tell the user.
- If the PR is already closed or merged, stop.

## Step 1 — Fetch inline review comment threads AND review summaries

Fetch both kinds of review feedback. Inline threads live under `pulls/{n}/comments`;
general review summaries (the free-form body attached to a review) live under
`pulls/{n}/reviews`.

```bash
# Inline comments (threads)
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate

# PR review summaries (non-inline bodies)
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews --paginate \
  --jq '.[] | select(.state != "PENDING") | {id, body, user: .user.login, state}'
```

Group inline comments into threads:

- Build a map of `id → comment`
- A comment with no `in_reply_to_id` is a **thread root**
- Comments with `in_reply_to_id` are replies to the root

Process **thread roots only**. For inline threads, skip a thread if:

- `author_association` is `"BOT"` or the login contains `[bot]`
- `position` is `null` (outdated diff line — the code changed since the comment was posted)
- The current git user (`git config user.name`) has already replied in that thread

For review summaries, treat each non-empty non-`PENDING` review body as a
separate item to triage (it is not a thread — the reviewer left a comment on the
PR as a whole, e.g. "CHANGELOG not updated"). Skip summaries that are empty or
bot-authored. Note whether you have already replied to a given summary by
checking for a later `COMMENTED`/submitted review from the current user.

Get the current user's login for filtering:

```bash
gh api user --jq '.login'
```

If nothing remains after filtering, there is nothing to fix — but the review still needs to be acknowledged. Skip Steps 2–6 and go straight to **Step 7** to swap the label (this marks that the implementer processed the review), then tell the user there was nothing to address and stop.

## Step 2 — Assess each thread

For each thread root, in sequence:

1. **Read the code context**: Use the `Read` tool on `comment.path`, centered around `comment.line` (±15 lines). If the file doesn't exist locally, note it and move on.

2. **Evaluate**:
   - Is the feedback technically correct for this codebase?
   - Is it YAGNI — calling out code that genuinely isn't needed?
   - Does it conflict with prior architectural decisions visible in the codebase?
   - Is it ambiguous — you'd need more information to act safely?

3. **Assign a decision**:
   - `FIX` — feedback is valid; apply a change
   - `DECLINE` — feedback is technically wrong, YAGNI, or contradicts a sound existing decision
   - `CLARIFY` — too ambiguous to act on; must ask the reviewer first

Keep your reasoning for each decision (one sentence).

## Step 3 — Show triage table (and optionally confirm)

Print this table before touching any code:

```
| # | Author | File:Line | Comment | Decision | Reason |
|---|--------|-----------|---------|----------|--------|
| 1 | alice  | src/api.ts:42 | "This should be async" | FIX | Correct — the call can block |
| 2 | bob    | lib/utils.ts:7 | "Add error handling here" | DECLINE | Already handled by caller; double-handling would swallow errors |
```

Truncate long comments to ~60 chars. For review summaries there is no file/line
anchor — use `PR` (or the review id) as the reference and include the summary's
full text so the user can judge it.

**Interactive mode (no `--auto`):** Stop here and wait for user confirmation before making any code changes or posting any replies. If the user wants to override a decision, update your plan accordingly.

**Routine mode (`--auto`):** Log the triage table and proceed immediately to Step 4 without waiting. Apply all `FIX` decisions as assessed; do not second-guess unless the edit would require deleting a file or making a breaking API change (in those cases, skip and log a note).

## Step 4 — Apply fixes

For each `FIX` item, apply the code change with the `Edit` tool. Make minimal, targeted changes — exactly what the comment asks for, nothing more.

After all edits, if a `qa-check` skill or similar quality pipeline is available, run it and surface any failures before proceeding.

## Step 5 — Commit and push

Stage only the files that were modified (never `git add -A` or `git add .`):

```bash
git add path/to/file1 path/to/file2
git commit -m "$(cat <<'EOF'
fix: address PR review comments

- <one bullet per FIX, referencing file and what changed>

EOF
)"
git push
```

## Step 6 — Reply to every thread

Post a reply to **every** thread root (FIX, DECLINE, and CLARIFY):

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
  -f body="<reply text>"
```

Note: include `{pr_number}` in the path — omitting it returns 404.

For PR **review summaries** (which are not threads), there is no inline replies
endpoint. Reply by posting a new COMMENT review on the PR referencing the
summary and the outcome:

```bash
gh api --method POST repos/{owner}/{repo}/pulls/{pr_number}/reviews \
  -f body="<reply text>" \
  -f event="COMMENT" \
  --jq '.html_url'
```

**Reply rules** — terse, technical, no performative language:

| Decision | Reply format |
|----------|-------------|
| FIX | `"Fixed in {file}:{line}. {one sentence describing what changed}."` |
| DECLINE | `"{Technical reason the current implementation is correct or why the change is YAGNI}."` |
| CLARIFY | `"Need clarification: {specific question}. Holding off until answered."` |

Never write: "Thanks!", "Great catch!", "You're right!", "Good point!", or any gratitude or praise.
Never write: "I've gone ahead and…" or "Let me…" — state the outcome directly.

## Step 7 — Update PR labels (mandatory — do not skip)

**This step is not optional cleanup.** The skill is not finished until it has
run. Skipping it silently blocks the PR pipeline downstream: nothing else
watching this PR (an orchestrator, a human, another skill) has any other
signal that the review was actually addressed, and the PR will sit stuck on
`reviewed` even though the work is done.

Run this even when Step 1 found no threads or summaries to address — swapping the
label is the process signal that the implementer acknowledged the review,
independent of whether any fixes were needed:

```bash
gh pr edit [PR#] --remove-label "reviewed" --add-label "ready-to-merge"
```

If the PR doesn't have the `reviewed` label (e.g. the review was done outside
this skill's flow), the `--remove-label` will no-op safely — still add
`ready-to-merge`.

**Before reporting this skill as done, verify the label actually changed:**

```bash
gh pr view [PR#] --json labels -q '[.labels[].name]'
```

If `ready-to-merge` is not in the result, the edit did not take — go back and
re-run it. Do not describe the run as complete while this is still pending.

## Step 8 — Print summary

Include whether the label swap in Step 7 was confirmed — don't just list the
comment-level outcomes:

```
| # | File:Line | Decision | Reply posted |
|---|-----------|----------|-------------|
| 1 | src/api.ts:42 | FIX | ✓ |
| 2 | lib/utils.ts:7 | DECLINE | ✓ |

Label: ready-to-merge ✓ confirmed
```

---

## Mindset

Apply the `receiving-code-review` principle throughout:

- **Verify before implementing** — check the code before agreeing.
- **Push back technically** — if a suggestion breaks things or is YAGNI, say so clearly.
- **Never blind-implement** — an external reviewer may lack full context.
- **Actions over words** — the code change and the reply are the acknowledgment.
- **The label swap is part of the job, not a footnote** — a review addressed but not marked `ready-to-merge` is indistinguishable, to everything downstream, from a review nobody looked at.
