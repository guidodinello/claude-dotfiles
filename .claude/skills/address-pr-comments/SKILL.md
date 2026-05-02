---
name: address-pr-comments
description: >
  Address incoming PR review comments end-to-end: fetch all unresolved inline
  review threads, assess their validity, fix valid ones, commit and push, then
  reply to every thread with the outcome. Use when a PR has received review
  feedback that needs to be triaged and responded to.
---

# Address PR Comments

Automates the full loop for responding to inline PR review comments: fetch → assess → fix → commit → reply.

## Invocation

```
/address-pr-comments [PR#]
```

`PR#` is optional. Omit it to use the current branch's open PR.

## Step 0 — Resolve the PR

```bash
gh pr view [PR#] --json number,headRefName,baseRefName,url,state
gh repo view --json owner,name
```

- If no open PR is found, stop and tell the user.
- If the PR is already closed or merged, stop.

## Step 1 — Fetch inline review comment threads

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments --paginate
```

Group comments into threads:
- Build a map of `id → comment`
- A comment with no `in_reply_to_id` is a **thread root**
- Comments with `in_reply_to_id` are replies to the root

Process **thread roots only**. Skip a thread if:
- `author_association` is `"BOT"` or the login contains `[bot]`
- `position` is `null` (outdated diff line — the code changed since the comment was posted)
- The current git user (`git config user.name`) has already replied in that thread

Get the current user's login for filtering:
```bash
gh api user --jq '.login'
```

If no threads remain after filtering, tell the user there's nothing to address and stop.

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

## Step 3 — Show triage table and get confirmation

Print this table before touching any code:

```
| # | Author | File:Line | Comment | Decision | Reason |
|---|--------|-----------|---------|----------|--------|
| 1 | alice  | src/api.ts:42 | "This should be async" | FIX | Correct — the call can block |
| 2 | bob    | lib/utils.ts:7 | "Add error handling here" | DECLINE | Already handled by caller; double-handling would swallow errors |
```

Truncate long comments to ~60 chars.

**Stop here and wait for user confirmation** before making any code changes or posting any replies. If the user wants to override a decision, update your plan accordingly.

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

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
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

**Reply rules** — terse, technical, no performative language:

| Decision | Reply format |
|----------|-------------|
| FIX | `"Fixed in {file}:{line}. {one sentence describing what changed}."` |
| DECLINE | `"{Technical reason the current implementation is correct or why the change is YAGNI}."` |
| CLARIFY | `"Need clarification: {specific question}. Holding off until answered."` |

Never write: "Thanks!", "Great catch!", "You're right!", "Good point!", or any gratitude or praise.
Never write: "I've gone ahead and…" or "Let me…" — state the outcome directly.

## Step 7 — Print summary

```
| # | File:Line | Decision | Reply posted |
|---|-----------|----------|-------------|
| 1 | src/api.ts:42 | FIX | ✓ |
| 2 | lib/utils.ts:7 | DECLINE | ✓ |
```

---

## Mindset

Apply the `receiving-code-review` principle throughout:

- **Verify before implementing** — check the code before agreeing.
- **Push back technically** — if a suggestion breaks things or is YAGNI, say so clearly.
- **Never blind-implement** — an external reviewer may lack full context.
- **Actions over words** — the code change and the reply are the acknowledgment.
