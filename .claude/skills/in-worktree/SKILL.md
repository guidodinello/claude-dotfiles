---
name: in-worktree
description: >
  Run another skill inside an isolated git worktree instead of the current
  checkout, so multiple agentic tools (or multiple tasks) can work on this
  repo at the same time without touching each other's files. Supports a
  fresh branch off the repo's default branch, or checking out an existing PR's branch,
  and can seed the fresh worktree with an uncommitted local file (e.g. a
  just-approved PDR) before running the target skill. Use when the user
  wants to run a skill "in a worktree", "isolated", "on the side", or
  explicitly asks to work on something in parallel with other
  terminals/tools. Trigger phrases: "in a worktree", "isolate this", "run
  it on the PR branch", "don't touch my working tree".
---

# In Worktree

Composes isolation with any other skill: set up a git worktree, switch the
session into it, then run the target skill there. The target skill is
unmodified — it just operates on whatever the current working directory is.

This skill does not clean up after itself. The session stays in the
worktree when it finishes, since the point is to hand that terminal a
worktree of its own to keep working in.

## Invocation

```
/in-worktree [--pr <n> | --branch <name>] [--name <branch>] [--seed <path>] /<skill> [skill args…]
```

- No flags → **fresh mode**: new branch off `origin/<default-branch>` (resolved by `EnterWorktree` itself — see Step 2).
- `--pr <n>` → **PR mode**: worktree checks out PR `<n>`'s existing head branch.
- `--branch <name>` → **branch mode**: worktree checks out branch `<name>` (must already exist on the remote or locally).
- `--name <branch>` → only used in fresh mode, to name the new branch. Ignored (and ignorable) in PR/branch mode, since the branch name there comes from the PR/`--branch`.
- `--seed <path>` → after the worktree is created, copy this one file (path relative to `ORIGIN_CWD`) into the worktree at the same relative path, before running the inner skill. For uncommitted local state a fresh worktree cut from the default branch wouldn't otherwise have — e.g. a PDR approved locally but not yet pushed. Only meaningful in fresh mode; ignored in PR/branch mode (those checkouts already have everything committed to the branch).
- Everything from the first `/<skill>` token onward is passed through untouched — this skill does not parse or understand the inner skill's own arguments.

`--pr` and `--branch` are mutually exclusive. If both are given, stop and ask the user which they meant.

## Step 0 — Preflight

Record the current checkout's absolute path **before** switching anywhere — this is where the inner skill's instructions will be read from, regardless of which worktree ends up as the working directory:

```bash
ORIGIN_CWD=$(pwd)
```

Confirm the repo is clean enough to reason about and fetch latest refs:

```bash
git fetch origin
```

Do NOT require the current working tree to be clean — this skill doesn't touch the current checkout at all, it only reads from `origin` and creates a new worktree.

## Step 1 — Resolve the target skill and args

Split the invocation at the first token starting with `/`. Everything before it is this skill's own flags; everything from that token on (minus the leading `/`) is `INNER_SKILL` and `INNER_ARGS`.

If no `/<skill>` token is found, stop and tell the user what to invoke, e.g. `/in-worktree --pr 123 /address-pr-comments`.

Confirm the target exists, using `ORIGIN_CWD` explicitly — **not** a bare relative path — since by Step 3 the working directory will have moved to the worktree, and a relative `.claude/skills/...` would then resolve against the wrong tree:

```bash
test -f "${ORIGIN_CWD}/.claude/skills/${INNER_SKILL}/SKILL.md" || echo "ERROR: no such skill: ${INNER_SKILL}"
```

## Step 2 — Set up the worktree

All worktrees land under `.claude/worktrees/`, consistent with the rest of the repo.

### Fresh mode (default)

```
EnterWorktree name=<--name value, or a short descriptive name if omitted>
```

This is the native tool: with the default `worktree.baseRef: fresh` setting, it creates the worktree on a **new branch off `origin/<default-branch>`**, resolving the default branch dynamically rather than hardcoding it, and switches the session into it. Confirm the branch it created:

```bash
git branch --show-current
```

### PR mode (`--pr <n>`)

```bash
BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
```

Cross-fork PRs (head repo ≠ `${REPO}`) are out of scope for this skill — stop and tell the user to use `gh pr checkout` manually in that case.

Check whether another worktree already has this branch checked out (the multi-terminal collision case):

```bash
git worktree list | grep -F "[${BRANCH}]"
```

If found, stop and tell the user which path already has it — do not create a second checkout of the same branch.

Otherwise, create the worktree with a **tracking upstream**, so a later bare `git push` from inside it lands correctly:

```bash
WORKTREE_PATH=".claude/worktrees/pr-<n>-${BRANCH##*/}"
git worktree add --track -b "${BRANCH}" "${WORKTREE_PATH}" "origin/${BRANCH}"
```

If `git worktree add` fails because the local branch `${BRANCH}` already exists (e.g. left over from a previous session), use instead:

```bash
git worktree add "${WORKTREE_PATH}" "${BRANCH}"
```

Then switch the session in:

```
EnterWorktree path="${WORKTREE_PATH}"
```

### Branch mode (`--branch <name>`)

Same as PR mode, but skip the `gh pr view` lookup — use `<name>` directly as `${BRANCH}` and derive `WORKTREE_PATH=".claude/worktrees/${BRANCH}"`.

### Seeding (`--seed <path>`, fresh mode only)

The worktree is now the working directory. Copy the seed file in from `ORIGIN_CWD`, preserving its relative path:

```bash
SEED_REL=$(realpath --relative-to "${ORIGIN_CWD}" "${ORIGIN_CWD}/<path>")
dest="./${SEED_REL}"
mkdir -p "$(dirname "$dest")"
cp "${ORIGIN_CWD}/${SEED_REL}" "$dest"
```

Copy **only the one file named by `--seed`** — never the whole directory it lives in (e.g. don't also copy a README index alongside it). If the inner skill needs to update sibling files (like an index), it should do so inside the worktree itself once it's running there.

## Step 3 — Run the inner skill

Read `"${ORIGIN_CWD}/.claude/skills/${INNER_SKILL}/SKILL.md"` in full — **from `ORIGIN_CWD`, not the worktree** — and follow its instructions, treating `INNER_ARGS` as that skill's own invocation arguments.

This split matters: the skill's *instructions* come from the checkout the user is actually working in (so a skill edited but not yet committed, or simply not yet present on `origin/main` / an older PR branch, still runs correctly). Only the skill's *target data* — the code it reads, edits, greps, and commits — should come from the worktree, because the working directory is now the worktree and every bare `git`, `gh`, `Read`, and `Edit` the inner skill performs during execution is scoped to it automatically. Reading the instructions from the worktree instead would silently run a stale or missing version of the skill whenever the worktree's `.claude/skills/` differs from the checkout's.

## Step 4 — Report

After the inner skill finishes, report:

- The worktree path and branch the session is now in.
- That the session has been left inside the worktree (not returned to the original checkout) — this terminal now owns that worktree for further work.
- The cleanup command for when the user is fully done with this line of work, to run from the main checkout:

  ```bash
  git worktree remove <path> && git branch -d <branch>
  ```

## Notes

- This skill works with any skill that operates on the current working directory — which is all of them, including `feature-workflow` (e.g. `/in-worktree --seed docs/process/pdr/004-my-feature.md /feature-workflow docs/process/pdr/004-my-feature.md`).
- `--pr`/`--branch` mode assumes the branch already has an upstream on `origin` — it is for continuing work on something that already exists remotely, not for starting something new (use fresh mode for that).
