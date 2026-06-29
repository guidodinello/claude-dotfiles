---
name: opencode-code-review
description: Review a GitHub pull request using parallel task subagents (model-agnostic, works with opencode free tier). Does NOT auto-post comments — returns findings to the user. Use whenever the user says "review this PR", "code review", "check this pull request", or pastes a PR URL.
---

# Code review (Opencode)

Provide a code review for the given pull request. Do NOT post any comments on the PR — return findings to the user.

## Setup

Before reviewing, create a worktree for the PR:

1. Fetch the PR metadata from GitHub to get the head branch and base branch.
2. Create the worktree: `git worktree add .claude/worktrees/pr-XXXX origin/<head-branch>`
3. In the worktree, set the upstream to the PR base: `git branch --set-upstream-to=origin/<base-branch>`
4. Run the review from the worktree.

## Steps

1. **Eligibility check** — Use a task subagent (type: `explore`) to check if the PR (a) is closed, (b) is a draft, (c) does not need a review (automated, trivial, or already reviewed by you). If so, stop and tell the user.

2. **Gather CLAUDE.md files** — Use another task subagent (type: `explore`) to list file paths of any relevant CLAUDE.md files: the root CLAUDE.md, plus any in directories the PR modified.

3. **Summarize the PR** — Use a task subagent (type: `explore`) to view the PR and return a summary of the change.

4. **Parallel review (5 subagents)** — Launch 5 parallel task subagents (type: `general`) to independently review the change. Each returns a list of issues and why each was flagged:
   - Agent #1: CLAUDE.md compliance (note: not all CLAUDE.md instructions apply during review)
   - Agent #2: Obvious bugs in the diff (shallow scan, no extra context, focus on real bugs not nits)
   - Agent #3: Git blame/history of modified code — bugs in light of historical context
   - Agent #4: Previous PRs touching these files — check for comments that may apply again
   - Agent #5: Code comments in modified files — ensure changes comply with inline guidance

5. **Score issues** — For each issue from step 4, launch a parallel task subagent (type: `general`) with the PR, issue description, and CLAUDE.md files (from step 2). Score each 0–100 using this rubric (pass verbatim):
   - 0: Not confident at all. False positive, doesn't stand up to light scrutiny, or pre-existing.
   - 25: Somewhat confident. Might be real but unverified. Stylistic issues not called out in CLAUDE.md.
   - 50: Moderately confident. Real but nitpicky or unlikely in practice. Not very important.
   - 75: Highly confident. Double-checked and verified real and impactful. Directly violates CLAUDE.md.
   - 100: Absolutely certain. Confirmed real, will happen frequently. Evidence directly confirms.

6. **Filter** — Remove issues with score < 80. If none remain, tell the user.

7. **Return findings to the user** — Present the filtered issues with:
   - Brief description of each issue
   - Link to file and line (full SHA, e.g. `https://github.com/owner/repo/blob/<sha>/path/to/file#L10-L15`)
   - What flagged it (CLAUDE.md, bug pattern, historical context, etc.)
   - Keep output brief, no emojis

## False positive examples (for steps 4–5)

- Pre-existing issues
- Something that looks like a bug but isn't
- Pedantic nitpicks a senior engineer wouldn't call out
- Issues a linter/typechecker/compiler would catch (missing imports, type errors, formatting). Assume CI runs these.
- General code quality issues (test coverage, security, docs) unless CLAUDE.md requires them
- Issues silenced by lint ignore comments
- Intentional functionality changes related to the broader change
- Real issues on lines the user didn't modify

## Notes

- Do not check build signal or attempt to build/typecheck. CI handles that.
- Use `gh` to interact with GitHub (view PR, fetch diff), not web fetch.
- Make a todo list first.
- Cite and link each issue.
- **Do NOT use `gh pr comment` or any other method to post on the PR.** Return findings to the user.
- Use the `task` tool with `subagent_type: "general"` for review/analysis work and `subagent_type: "explore"` for lookup/eligibility/summary work.
