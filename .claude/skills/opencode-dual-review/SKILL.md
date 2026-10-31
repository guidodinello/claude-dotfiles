---
name: opencode-dual-review
description: "Trigger: opencode review, dual review, free-model review, second opinion on a PR. Two free opencode models each post their own untriaged inline-comment review (blocking/non-blocking tiers, full-SHA permalinks) to the PR, with one Claude Sonnet medium-effort review as fallback. Triage happens later, in the address-pr-comments pass."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when the user asks for an opencode review, a dual or free-model review, or a second opinion on a PR before or alongside the native `code-review` skill.

Two free `opencode/*` models each review the same PR diff independently. Each one's findings are posted straight to the PR as its own **inline-comment review** the moment it succeeds, via `gh api .../pulls/{pr}/reviews`, with no Claude triage and no confirmation gate in between. This is intentional: wrong findings are expected and get declined later, like any other reviewer's comment, instead of being filtered out before anyone sees them.

Not for triage. Triage happens in the `address-pr-comments` pass on the same PR (see Steps).

## Helper scripts

The skill runs from the project's working directory, so always call the scripts by their installed absolute path (`$HOME`, not `~`, so it expands inside quotes):

```bash
ODR="$HOME/.claude/skills/opencode-dual-review/scripts"
"$ODR/review-pr.sh" <repo-dir> <pr-number> [diff-base-ref]
```

| Script | Role |
|---|---|
| `review-pr.sh` | Entry point. Picks opencode or Sonnet (see Decision Gates) and runs the review from a fresh detached worktree, so the caller's checkout may be dirty |
| `dual-review.sh` | Builds the prompt, runs both opencode slots in parallel, posts each review. Needs a clean tree; `review-pr.sh` provides one |
| `sonnet-review.sh` | Fallback: one `claude -p --model sonnet --effort $SONNET_EFFORT` (default `medium`) run with no tools, fed the exact prompt `dual-review.sh` builds |
| `post_structured_review.py` | Parses `---FINDING-START---` blocks and posts them as one GitHub review |

Running any `.sh` script with no arguments prints its usage and exits before touching anything.

## Hard Rules

- **Never post without a verdict.** A model output counts only if it contains `NO_FINDINGS` or a `---FINDING-START---` block. A model that spends its turn on rejected tool calls exits 0 with no verdict; posting that would publish a false "No issues found".
- **The model runs locked down.** It runs from an empty sandbox directory outside any repo (a project `opencode.json` in the PR checkout would outrank `OPENCODE_CONFIG`) with a locked config: `bash/read/glob/grep/list` are `ask`, which `opencode run` auto-rejects (`deny` on bash or read makes the free tier refuse the request), and everything else is `deny`. If the output shows a tool actually ran, the review is discarded, never posted.
- **In-repo CLAUDE.md is read from the committed tree.** It is read with `git show HEAD:<path>` and only when its mode is a regular file, never through the working tree: a PR could commit CLAUDE.md as a symlink to any file on the machine.
- **Python helpers run with `python3 -I`**, so a PR checkout cannot shadow a stdlib module.
- **One unanchorable finding must not sink the review.** Only a file and new-side line present in the PR diff becomes an inline comment; everything else goes in the review body under "Outside the diff", with its permalink. GitHub rejects the whole review (422) if any inline comment points outside the diff.
- **Never use `git diff` against a possibly diverged base branch** for the PR's diff; it once produced a 385-file false diff. Use `gh pr diff`. The one exception is the explicit `diff-base-ref` below.

## Decision Gates

| Condition | Action |
|---|---|
| `OPENCODE_SLOTS` is not `1` (the default since 2026-10-27) | Straight to Sonnet. opencode v2.1.4's `execute` tool runs model-written JavaScript with full filesystem access, and no `permission` or `tools` key in the locked config stops it (`deny`, `ask` and `tools.execute: false` were all tested). The review runs also load the global opencode config (MCP servers, plugins). Re-enable only once the slots are isolated |
| Diff over `SONNET_DIRECT_LINES` (default 1500) | Straight to Sonnet: the free models never finish at that size |
| Both opencode slots end with model `none` | One Sonnet medium-effort review. Never run Sonnet on top of a working opencode review |
| One slot `none`, the other posted | Report it plainly; do not present a partial review as complete. Do not re-run silently; let the user decide |
| PR stacked on an unmerged sibling branch | Pass `diff-base-ref` (e.g. `origin/feature/sibling`, named exactly): GitHub's diff still carries the sibling's commits, so review `<diff-base-ref>...HEAD` |
| Repo has no CLAUDE.md of its own | Fall back to an ancestor CLAUDE.md (see Configuration) |

## Configuration

All optional, set as environment variables on the call.

| Variable | Default | Effect |
|---|---|---|
| `REVIEW_CLAUDE_MD` | unset | Explicit fallback CLAUDE.md path, used when no in-repo CLAUDE.md applies. Skips the ancestor walk |
| `REVIEW_CLAUDE_MD_SECTIONS` | unset (whole file) | `\|`-separated heading prefixes (`## Heading`) to inline from the fallback file. An entry `<file>=## Heading` applies only when the repo root has `<file>` |
| `CODE_REVIEW_SKILL` | `$HOME/.claude/skills/code-review/SKILL.md` | Source of the shared false-positive list |
| `MAX_DIFF_LINES` | 4000 (20000 for Sonnet) | Diff lines inlined in the prompt |
| `MODEL_TIMEOUT_SECS` | 150 | Per-attempt timeout |
| `ATTEMPTS_PER_MODEL` | 1 | Attempts before a slot advances |
| `REVIEW_BUDGET_SECS` | 480 | Wall-clock budget per slot |
| `SONNET_DIRECT_LINES` | 1500 | Diff size that skips opencode |
| `SONNET_EFFORT` | `medium` | `--effort` for the Sonnet review (`low`, `medium`, `high`) |
| `OPENCODE_SLOTS` | `0` | `1` runs the opencode slots again. Leave it off until `execute` and the global config are locked out of review runs |

### CLAUDE.md fallback

When no in-repo CLAUDE.md applies (none in any changed file's directory up to the repo root), the script looks above the repo: it starts at the parent of the repo's **main checkout** (from `git rev-parse --git-common-dir`) and walks up to `/`, taking the first `CLAUDE.md` it finds. Starting at the main checkout, not at `<repo-dir>`, matters twice: `review-pr.sh` reviews from a detached worktree under `mktemp`, which has no useful ancestors, and starting above every checkout means the PR cannot plant the file that gets read.

Without `REVIEW_CLAUDE_MD_SECTIONS` the whole file is inlined (HTML comments stripped), then the shared 8000-character cap truncates it. For a large multi-repo workspace CLAUDE.md, name the sections instead, for example:

```bash
REVIEW_CLAUDE_MD_SECTIONS='## Engineering standards|## Code comments|composer.json=## PHP standards|package.json=## Frontend testing' \
  "$ODR/review-pr.sh" <repo-dir> <pr-number>
```

Without any fallback, the prompt promised guidance "below" that was not there, and models burned their turn trying to read CLAUDE.md with tools they do not have.

## Model order

- Slot A primary: `big-pickle`
- Slot B primary: `muse-spark-1.2-contributor-free`
- Shared fallback chain, in order: `nemotron-3-ultra-free` → `mimo-v2.5-free` → `hy3-free` → `nemotron-3.5-lightning-free`
- One attempt per model by default, then the slot advances. A model already used by the other slot is skipped, so the two reviews stay independent.

The skill assumes only the free `opencode/*` models are available. They are flaky; the fallback chain and the Sonnet fallback exist to absorb that.

## What the prompt covers

Each model gets a single prompt with no follow-up tool calls, so `dual-review.sh` gathers everything up front. It mirrors `code-review`'s dimensions as far as a toolless model allows:

1. CLAUDE.md compliance: every CLAUDE.md from each changed file's directory up to the repo root (first 15 changed files, 8000 chars total), else the fallback above.
2. Obvious bugs in the diff.
3. Git blame/history: for each changed file, blame of the old-side line ranges at the merge-base plus the file's last 2 pre-PR commits.
4. Previous PR comments on the same files: each file's recent pre-PR commits are resolved to merged PRs via `gh api repos/{owner}/{repo}/commits/{sha}/pulls`, and review comments anchored to a changed file are pulled (5 distinct PRs max).
5. The shared false-positive list, read at runtime from `code-review`'s own `SKILL.md` (`Examples of false positives` section), so the two skills cannot drift. A minimal built-in list is used if the file is missing.

Deliberately not replicated: `code-review`'s separate per-finding confidence scoring pass. Each model self-tiers its findings in the same pass; a second call per finding would double runtime on already flaky models.

The posted format matches `code-review`: a review body with blocking/non-blocking counts and a harness/model attribution line, one inline comment per finding anchored to `file:line` with a `**[blocking]**`/`**[non-blocking]**` prefix and a full-SHA permalink. Zero findings posts the "No issues found" review.

## Steps

1. Run `review-pr.sh <repo-dir> <pr-number> [diff-base-ref]` with any configuration the project needs. It checks out the PR (`gh pr checkout --detach`) in a temporary worktree, pulls the diff with `gh pr diff`, inlines it into the prompt, runs both slots in parallel, and removes the worktree. Each slot posts its own review as soon as it succeeds. If posting fails, the slot prints `ERROR: posting the review … failed; findings are in <file>`.
2. Report which model produced each review (it may not be the primary: read the `[A]`/`[B] succeeded with <model>` lines, or `model_A.txt`/`model_B.txt` in the printed output dir) and how many blocking and non-blocking findings each posted, or that Sonnet ran instead and why. That ends this skill's job.
3. When the user is ready (possibly another session): run `address-pr-comments` on the same PR. It fetches every unresolved thread, including these reviews, verifies each against the code, fixes what is real and declines the rest. Its label-swap step no-ops harmlessly in repos without its `reviewed`/`ready-to-merge` labels.

## Cross-checking is not optional

Free models report plausible but unverified absences. In an early run one model called a PR incomplete because a storage disk config and its env vars were "absent", while the other model had found both already in the repo. Never forward a "missing X" finding without checking `X` yourself first; it is the most common way these models look authoritative while being wrong.

## Output Contract

Reply in the conversation language: per slot, the model that posted (or `none`) and its blocking and non-blocking counts; whether Sonnet ran and why; the output dir with the raw transcripts.
