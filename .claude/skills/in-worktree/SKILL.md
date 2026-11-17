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

The session stays in the worktree when it finishes, since the point is to
hand that terminal a worktree of its own to keep working in. Tear it down
afterwards with `scripts/teardown.py` (see [Teardown](#teardown)).

## Invocation

```
/in-worktree [--pr <n> | --branch <name>] [--name <branch>] [--seed <path>] [--deps <dir>]… /<skill> [skill args…]
```

- `--deps <dir>` → repeatable. Node dependencies (`node_modules`) are only set up for lockfile directories the task needs: in PR/branch mode, those the branch diff touches; in fresh mode, only those named by `--deps` (e.g. `--deps frontend/web`). A backend-only task therefore gets no `frontend/web/node_modules`. See [Dependencies](#dependencies-lockfile-driven).

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

### Dependencies (lockfile-driven)

Make sure dependency trees are usable before any inner skill runs typecheck, lint or tests. Detect them from the lockfiles instead of hard-coding paths: for each tracked lockfile, symlink the dependency directory from `ORIGIN_CWD` when the lockfile is byte-identical there (instant, and an identical lockfile guarantees identical resolved deps), otherwise install fresh.

Two guards keep this cheap on a small disk:

- **Node dependencies are opt-in per lockfile directory.** `NODE_DIRS` is the newline-separated list of paths the task touches: the `--deps` values in fresh mode, or the files in `git diff --name-only "origin/<default>...HEAD"` in PR/branch mode. Any other Node lockfile directory is skipped with a log line. `uv.lock` is not gated by `NODE_DIRS` (uv hardlinks from its cache), but it is subject to the free-disk guard below.
- **A real install needs free disk.** Below `MIN_FREE_GB` (default 5) the install is skipped with a warning. Never push with `SKIP=` to get past a hook that needs the missing dependencies; free space or set the dependencies up, then push.

Before the loop, set `NODE_DIRS` to one path per line: fresh mode → the `--deps` values, one per line (e.g. `NODE_DIRS=$(printf '%s\n' frontend/web)`); PR/branch mode → `NODE_DIRS=$(git diff --name-only "origin/<default>...HEAD")`. A Node lockfile directory is set up when any listed path equals it or lies under it. The block is plain POSIX plus `<<<` and `< <(…)`, so it runs unchanged in bash and zsh (zsh does not word-split unquoted variables, so it iterates lines, never `for p in $VAR`).

```bash
NODE_DIRS="${NODE_DIRS:-}"          # e.g. "frontend/web"; empty = no Node deps
MIN_FREE_GB="${MIN_FREE_GB:-5}"
while IFS= read -r lock; do
  dir=$(dirname "$lock"); name=$(basename "$lock")
  case "$name" in
    pnpm-lock.yaml)    dep=node_modules; node=1; install="pnpm install --frozen-lockfile --prefer-offline" ;;
    package-lock.json) dep=node_modules; node=1; install="npm ci --prefer-offline" ;;
    yarn.lock)         dep=node_modules; node=1; install="yarn install --frozen-lockfile --prefer-offline" ;;
    uv.lock)           dep=.venv;        node=0; install="uv sync" ;;
    *) continue ;;  # unknown lockfile: leave it to the inner skill
  esac
  if [ "$node" = 1 ]; then
    needs=0
    while IFS= read -r p; do
      [ -n "$p" ] || continue
      if [ "$dir" = . ]; then needs=1; else case "$p" in "$dir"|"$dir"/*) needs=1 ;; esac; fi
    done <<< "$NODE_DIRS"
    [ "$needs" = 1 ] || { echo "skipped $dir: task does not touch it (set NODE_DIRS=$dir to set it up)"; continue; }
  fi
  [ -e "$dir/$dep" ] && continue   # already present
  if cmp -s "${ORIGIN_CWD}/$lock" "$lock" && [ -d "${ORIGIN_CWD}/$dir/$dep" ]; then
    ln -s "${ORIGIN_CWD}/$dir/$dep" "$dir/$dep"
  else
    free_gb=$(( $(df -Pk "$dir" | awk 'NR==2 {print $4}') / 1048576 ))
    if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
      echo "WARNING: only ${free_gb} GB free (< ${MIN_FREE_GB}); skipped install in $dir"; continue
    fi
    (cd "$dir" && eval "$install")   # eval: zsh would not split $install into words
  fi
done < <(git ls-files '*pnpm-lock.yaml' '*package-lock.json' '*yarn.lock' '*uv.lock')
```

pnpm already hardlinks from its shared store (`pnpm store path`), so `du` on a worktree's `node_modules` overstates its real cost; the expensive part is the install run itself, which is why it is gated above.

A symlinked `node_modules` or `.venv` is shared with the origin checkout: don't run an install or `uv sync` inside the worktree for it without first replacing the symlink with a real directory. Teardown unlinks these symlinks and never touches the origin's directory.

### Per-repo setup hook (`scripts/bootstrap-worktree.sh`)

A repo that needs more than dependencies in a fresh worktree (a test database, ports of its own) ships `.claude/skills/in-worktree/scripts/bootstrap-worktree.sh` and its counterpart `teardown-worktree.sh`. If the repo has the setup script, run it with the **absolute** worktree path once the worktree exists, and before any agent starts in it:

```bash
git worktree add … <abs-worktree>                                   # 1. create (or EnterWorktree)
bash <repo>/.claude/skills/in-worktree/scripts/bootstrap-worktree.sh <abs-worktree>   # 2. set up
herdr workspace create --cwd <abs-worktree> …; herdr agent start …  # 3. start the agent
```

herdr has no "Setup Script" field (Orca does), so the order above is the caller's job: the spawning orchestrator, or this skill in Step 2. Stop and report if the script fails; do not start the agent on a half-set-up worktree. The script must be idempotent and must refuse the main checkout.

The matching teardown runs from `teardown.py`, before it removes the worktree (see [Teardown](#teardown)). What the pair sets up, and how to use it, is documented in the script headers and the repo's own docs.

## Step 3 — Run the inner skill

Read `"${ORIGIN_CWD}/.claude/skills/${INNER_SKILL}/SKILL.md"` in full — **from `ORIGIN_CWD`, not the worktree** — and follow its instructions, treating `INNER_ARGS` as that skill's own invocation arguments.

This split matters: the skill's *instructions* come from the checkout the user is actually working in (so a skill edited but not yet committed, or simply not yet present on `origin/main` / an older PR branch, still runs correctly). Only the skill's *target data* — the code it reads, edits, greps, and commits — should come from the worktree, because the working directory is now the worktree and every bare `git`, `gh`, `Read`, and `Edit` the inner skill performs during execution is scoped to it automatically. Reading the instructions from the worktree instead would silently run a stale or missing version of the skill whenever the worktree's `.claude/skills/` differs from the checkout's.

## Step 4 — Report

After the inner skill finishes, report:

- The worktree path and branch the session is now in.
- That the session has been left inside the worktree (not returned to the original checkout) — this terminal now owns that worktree for further work.
- The cleanup command for when the user is fully done with this line of work, to run from the main checkout (see [Teardown](#teardown)):

  ```bash
  python3 -I <skill-dir>/scripts/teardown.py <path> --label <herdr-label>
  ```

## Teardown

`scripts/teardown.py WORKTREE [--label LABEL] [--force] [--dry-run]` (stdlib Python, run with `python3 -I`; path relative to this skill's directory). Run it from the main checkout or the orchestrator, never from inside the worktree or from the herdr workspace being closed. Start with `--dry-run` to see the plan.

**`herdr workspace close` takes a workspace id, not a label.** Closing by label fails silently. The script resolves the id from the label and verifies the close.

If the repo has a `scripts/teardown-worktree.sh` (looked up in the main checkout, then in the worktree), `teardown.py` runs it before removing the worktree, and logs "skipping" when there is none. With `--label` it runs after the workspace is closed; without it nothing closes the workspace, so stop the agent first. It stays before the removal because the hook may be the worktree's own copy, which the removal deletes. If the removal then fails, re-run the repo's setup script (`bootstrap-worktree.sh <worktree>`, idempotent) to recreate what the hook removed. A failing hook never blocks the removal, so check its logged output: a hook that could not clean up warns and leaves the resources behind, and has to be re-run by hand.

The script's docstring (`python3 -I <skill-dir>/scripts/teardown.py --help`) owns the refusals, the order of actions, `--force` and the exit codes. Two things worth knowing here: the local branch is deleted only when its PR is merged, and `--force` skips the uncommitted-changes check, so use it only when that is intended. Tests: `python3 -I <skill-dir>/scripts/test_teardown.py`.

## Notes

- This skill works with any skill that operates on the current working directory — which is all of them, including `feature-workflow` (e.g. `/in-worktree --seed docs/process/pdr/004-my-feature.md /feature-workflow docs/process/pdr/004-my-feature.md`).
- `--pr`/`--branch` mode assumes the branch already has an upstream on `origin` — it is for continuing work on something that already exists remotely, not for starting something new (use fresh mode for that).
