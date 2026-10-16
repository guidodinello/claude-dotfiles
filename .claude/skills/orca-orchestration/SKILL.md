---
name: orca-orchestration
description: "Trigger: orchestrate subtasks with orca, implementer sessions or workers in worktrees, supervise waves of PRs, resume an orchestration run. Land a story's technical subtasks through Claude Code implementer sessions in Orca worktrees (opusplan, plan mode), answering their plans from one orchestrator session, supervising via transcripts, reviewing and merging their PRs, with a per-project docs folder."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when the user wants one orchestrator session to land several technical subtasks through Claude Code implementer sessions ("workers") in Orca worktrees: launching them in plan mode, answering their plans and questions, supervising them from their transcripts, reviewing and merging their PRs, and shipping the result. Also load to resume such a run.

Not for a single change the current session can make itself, and not for running reviews alone (use the project's review skill).

The method lives here and in [references/method.md](references/method.md). Everything project-specific (repos, base branches, merge strategy, branch-name rules, issue-tracker statuses and automation quirks, review tool, stack commands, per-repo brief rules, design tokens, lessons) lives in a per-project docs folder that this skill reads, writes on first run, and updates after every run. Never put project-specific content in this skill.

## Helper scripts

The orchestrator runs from the project's working directory, so call the scripts by their installed absolute path. Use exactly this invocation, so one permission rule matches it:

```bash
python3 -I <home>/.claude/skills/orca-orchestration/scripts/<script>.py ...
```

`<home>` is the expanded home directory, written literally (the auto-mode classifier matches the literal command). The profile records the expanded form.

| Script | Use |
|---|---|
| `wstat.py <worker> [chars]` | Pending tool and last text from a worker's transcript. Exit 2 before the first transcript write |
| `wwatch2.py <minutes> <worker>...` | Block until READY (plan or question), PR, IDLE, STUCK, NOTRANSCRIPT or TIMEOUT. Run it in the background |
| `wplan.py <worker>` | Print the latest `ExitPlanMode` plan |
| `fb.sh <handle> "<text>"` | Pick "Tell Claude what to change" (option 3) on the plan menu and submit one short line |
| `tread.sh <handle> [lines]` | Tail an Orca terminal. Noisy for TUIs; prefer the transcript |
| `make-brief.py <run-dir> <task-key>` | Generate `.task-brief.md` from the run folder. A template: copy and adapt per project |

`<worker>` is the worktree's absolute path. The scripts derive the transcript dir the way Claude Code does: `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<path with every non-alphanumeric character replaced by "-">` (first 200 chars plus a hash suffix when longer). A transcript dir name, or a name relative to `$ORCA_WORKSPACES` (default `~/orca/workspaces`, sanitized the same way), is also accepted.

## Hard Rules

- **Never approve a plan you have not read.** Read it with `wplan.py`, check every answer you sent is folded in, then approve. Never script "wait for the menu, then approve".
- **Long text never goes through the terminal.** `orca terminal send` truncates it. Write answers to `<worktree>/.orchestrator-answers.md` and send a one-line pointer.
- **Menus and prompts are typed differently.** A menu choice is the bare option number (no `--enter`). A free-text prompt is the full text without `--enter`, then a separate bare Enter. Read the menu on screen before choosing: the same number means different things on different menus.
- **Decide or park.** Approve what follows the task, the design, the recorded decisions or what the user already decided. Park and ask the user on a product fork, a security or supply-chain call, legal copy, or an unforced deviation from the task. Log every call made on the user's behalf in the run doc.
- **Never `--no-verify`**, for workers or yourself. A pre-existing hook failure gets a minimal, separately committed fix, or a question to the user.
- **Merge only what the profile lets the orchestrator merge.** The final merge to the base branch, and anything the profile reserves for the user, stays the user's.
- **Close only sessions you launched** or tool-launched read-only reviewers. The user's own sessions stay open.
- **Durable state goes in the docs folder**, never only in the scratchpad: ids, notes, mockups, the run log. A new session gets a new scratchpad.
- **Synthetic data only** in briefs, screenshots and test fixtures, when the project handles personal or health data.

## Decision Gates

| Condition | Action |
|---|---|
| Docs folder missing | Bootstrap mode |
| Docs folder present | Run mode |
| A repo gets 2+ PRs for the story | Integration branch for that repo (see method §1) |
| A repo gets a single PR | It targets the base branch directly, no integration branch |
| A dependency is reviewed but not merged | Stack the dependent on it (merge commit in brief Step 0); PR base stays the integration branch |
| A dependency is neither reviewed nor merged | Wait; do not launch the dependent |
| New screen or sizeable UI change, and the profile enables design sign-off | Mockup and user sign-off before approving that worker's plan |
| Worker plan re-presented without your answers | Do not approve; point it at the answers file again |
| Question with a product, security, supply-chain or legal fork | Park it and ask the user |
| Repo-level gate that prompts for consent before commits is on | Stop before launching: workers stall at the prompt. Ask the user |

## Docs Folder Location

First match wins:

1. An explicit path argument.
2. `<root>/my-dev-things/orca-orchestration/` when `<root>/my-dev-things/` exists. `<root>` is `git rev-parse --show-toplevel` of the **session cwd**, or the cwd itself when it is not inside a git repo (a multi-repo workspace root). Do not use a product repo's root.
3. Otherwise ask the user for a path before creating anything.

Do not assume whether `my-dev-things/` is committed or gitignored.

## Execution Steps

### Bootstrap (folder missing)

1. Investigate: the repos in play and their remotes, default and base branches, branch-protection and merge-method rules, branch-name hooks and CI triggers, stack and test commands, how worktrees get dependencies and env files, the review tool, and the issue tracker's statuses and automations.
2. Ask the user, one question at a time, what code cannot tell: merge strategy per level, which merges the orchestrator may do, the tracker status flow and its automation quirks, who gets assigned, attribution policy, whether UI work needs design sign-off.
3. Write the folder from [references/docs-template.md](references/docs-template.md), show it, and wait for confirmation before the first run.

### Run (folder present)

1. Read the folder: the profile, `brief-rules/`, `gotchas.md`, and the latest run when resuming.
2. Confirm the kickoff contract with the user (method §0), then follow [references/method.md](references/method.md): pre-flight, integration branches, waves, optional design sign-off, launch, briefs, supervision loop, review and merge, verification and ship, cleanup.
3. Keep `runs/YYYY-MM-DD-<story>/README.md` current as you go: waves, workers, decisions made on the user's behalf, PRs, statuses.
4. Fold every new lesson into `gotchas.md` and, if a profile field was wrong or missing, the profile.

## Output Contract

Reply in the conversation language. While running: one short status line per event (worker, state, what you did). At the end: per worker, its PR and merge state; the integration PRs and ship order; the calls made on the user's behalf; what is left for the user; the run doc path and the lessons added.

## References

- [references/method.md](references/method.md): the procedure, phase by phase, and the generic gotchas table.
- [references/docs-template.md](references/docs-template.md): templates for the per-project docs folder.
- [scripts/make-brief.py](scripts/make-brief.py): brief generator template.
