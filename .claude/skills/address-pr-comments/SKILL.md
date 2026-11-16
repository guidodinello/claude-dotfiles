---
name: address-pr-comments
description: >
  Address incoming PR review comments end-to-end: fetch all unresolved inline
  review threads AND PR review summaries, assess their validity, fix valid ones,
  commit and push, reply to every thread (and each review summary) with the
  outcome, then resolve every thread that was fixed or declined (the merge
  ruleset blocks on unresolved threads). Use when a PR has received review
  feedback that needs to be triaged and responded to.
---

# Address PR Comments

Automates the full loop for responding to PR review comments: fetch → assess → fix → commit → reply → resolve.

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
- `{owner}` is `.owner.login` and `{repo}` is `.name` from the `gh repo view` output. Use
  those values everywhere below; never hardcode them.

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

Process **thread roots only**. Do **not** skip bot-authored threads (Copilot
included) or outdated threads (`position` is `null`): the `development` ruleset
blocks merge on ANY unresolved conversation, so they are triaged, replied to and
resolved like every other thread. For an outdated thread there is no
`line`; use `original_line` to find the code and check whether the current code
already addresses the comment (then reply with that fact and resolve, as FIX or
DECLINE as fits).

The only thread skipped for triage is one where the current git user
(`git config user.name`) has already replied (an earlier run). Do not re-reply, but
if it is still unresolved it is handled by **Step 6b** (earlier-run rule).

For review summaries, treat each non-empty non-`PENDING` review body as a
separate item to triage (it is not a thread — the reviewer left a comment on the
PR as a whole, e.g. "CHANGELOG not updated"). Skip summaries that are empty or
bot-authored. Note whether you have already replied to a given summary by
checking for a later `COMMENTED`/submitted review from the current user.
Summaries are not threads and cannot be resolved; Steps 6b and 6c do not cover them.

Get the current user's login for filtering:

```bash
gh api user --jq '.login'
```

If nothing remains after filtering, there is nothing to fix — but the review still needs to be acknowledged. Skip Steps 2–6, run **Steps 6b and 6c** (earlier-run threads may still be unresolved), then **Step 7** to add `ready-to-merge` (this marks that the implementer processed the review), then tell the user there was nothing to address and stop.

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

## Step 6b — Resolve threads (a reply is not enough)

The `development` ruleset sets `required_review_thread_resolution: true`. A PR
with green CI sits `BLOCKED` while **any** review thread is unresolved, and
replying does not resolve a thread. After replying, resolve explicitly.

Rules:

- `FIX` and `DECLINE` threads: resolve after the reply is posted.
- `CLARIFY` threads: leave open. They are the only threads that stay open.
- Earlier-run threads (the current user replied in a previous run and the thread is
  still unresolved): resolve them too, unless that reply starts with
  `Need clarification:`.
- Bot-authored (Copilot) and outdated threads follow the same rules as any other.

List the threads, then resolve one (same queries as the `babysit-prs` section
"Resolve review threads — a reply is not enough"; owner/repo come from Step 0,
and `databaseId` is added so a thread maps to the REST comment `id` used in
Steps 1 and 6):

```bash
# list threads: id (PRRT_...), state, and the root comment's REST id
gh api graphql \
  -f query='query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){pullRequest(number:$n){reviewThreads(first:100){nodes{id isResolved isOutdated comments(first:1){nodes{databaseId path body author{login}}}}}}}}' \
  -f owner="{owner}" -f name="{repo}" -F n={pr_number} \
  --jq '.data.repository.pullRequest.reviewThreads.nodes[]'

# resolve one
gh api graphql \
  -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' \
  -f id="<PRRT_id>"
```

Match each thread to its root comment by `comments.nodes[0].databaseId` ==
the REST comment `id`. If a PR has more than 100 threads, page with `after`.

## Step 6c — Final check: report unresolved threads

Run the list query again. Every thread must be `isResolved: true` except
`CLARIFY` threads. Report each remaining unresolved thread with a specific
reason: `waiting on author` (CLARIFY question posted), or `resolve failed`
(with the error). If a thread is unresolved for any other reason, resolve it
or fix the cause; do not report the run as done. Review summaries are not
threads and are not covered by this check.

## Step 7 — Update PR labels (mandatory — do not skip)

**This step is not optional cleanup.** The skill is not finished until it has
run. Skipping it silently blocks the PR pipeline downstream: nothing else
watching this PR (an orchestrator, a human, another skill) has any other
signal that the review was actually addressed, and the PR will sit at
`reviewed` without `ready-to-merge` even though the work is done.

Run this even when Step 1 found no threads or summaries to address — adding the
label is the process signal that the implementer acknowledged the review,
independent of whether any fixes were needed:

```bash
gh pr edit [PR#] --add-label "ready-to-merge"
```

Do **not** remove the `reviewed` label. `reviewed` (a review happened) and
`ready-to-merge` (the merge gate is passed) record separate facts and are
meant to coexist.

**Before reporting this skill as done, verify the label actually changed:**

```bash
gh pr view [PR#] --json labels -q '[.labels[].name]'
```

If `ready-to-merge` is not in the result, the edit did not take — go back and
re-run it. Do not describe the run as complete while this is still pending.

## Step 8 — Print summary

Include whether the label update in Step 7 was confirmed — don't just list the
comment-level outcomes:

```
| # | File:Line | Decision | Reply posted | Resolved |
|---|-----------|----------|--------------|----------|
| 1 | src/api.ts:42 | FIX | ✓ | ✓ |
| 2 | lib/utils.ts:7 | DECLINE | ✓ | ✓ |
| 3 | lib/x.ts:9 | CLARIFY | ✓ | open (waiting on author) |

Unresolved threads: 1 (#3 waiting on author)
Label: ready-to-merge ✓ confirmed
```

---

## Mindset

Apply the `receiving-code-review` principle throughout:

- **Verify before implementing** — check the code before agreeing.
- **Push back technically** — if a suggestion breaks things or is YAGNI, say so clearly.
- **Never blind-implement** — an external reviewer may lack full context.
- **Actions over words** — the code change and the reply are the acknowledgment.
- **The label update is part of the job, not a footnote** — a review addressed but not marked `ready-to-merge` is indistinguishable, to everything downstream, from a review nobody looked at.
