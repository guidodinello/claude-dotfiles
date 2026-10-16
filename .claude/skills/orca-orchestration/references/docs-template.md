# Per-project docs folder template

Layout, following the `dev-docs-index` convention (every folder has a `README.md`):

```
orca-orchestration/
  README.md            index + project profile
  gotchas.md           project-specific gotchas and lessons
  brief-rules/
    README.md          index
    common.md          rules every brief carries
    <repo>.md          per-repo rules
  runs/
    README.md          index of runs
    YYYY-MM-DD-<story>/
      README.md        run log
      ids.json         task ids, worktrees, branches, terminal handles
      make-brief.py    copied from the skill's scripts/, adapted
      task-<key>.md    task bodies, verbatim
      parent.md        parent story body, verbatim
      notes-common.md  coordination notes for every worker
      notes-<key>.md   coordination notes per worker
      mockup-v<n>/     signed-off design files, when design sign-off ran
```

## README.md

```markdown
# Orca orchestration: <project>

Profile and index for orchestrated implementer runs on <project>. Method: the `orca-orchestration` skill.

## Documents

| File | What it covers |
|---|---|
| `gotchas.md` | Project-specific gotchas and lessons |
| `brief-rules/README.md` | Rules pasted into every worker brief, per repo |
| `runs/README.md` | One folder per orchestration run |

## Profile

### Repos

| Repo | Orca repo id | Remote (`owner/repo`) | Base branch | Final merge method | Worktree Setup Script |
|---|---|---|---|---|---|
| <repo> | <id> | <owner/repo> | <base> | <squash / merge> | <what it installs, where it lives> |

### Branches and merges

- **Integration branch rule**: <only when a repo gets 2+ PRs for the story / always / never>
- **Integration branch name**: <e.g. feature/<ticket-id>/<slug>>
- **Child branch name and hook regex**: <allowed types per repo, e.g. `feature|bugfix|...`; how many path segments automations expect>
- **Child → integration merge**: <merge commit>
- **Integration → base merge**: <squash, by whom>
- **Merges the orchestrator may do**: <reviewed children into the integration branch>
- **Merges reserved for the user**: <final merge to base, infra repos, anything waiting on sign-off>
- **CI scope**: <which PR bases trigger CI; children targeting the integration branch may get none>
- **Ship order across repos**: <default order, and when a wire-contract change forces one window>

### Issue tracker

- **Tracker and how to read a task**: <tracker, CLI or MCP tool, and the command that prints a task body>
- **Assignee for created tasks**: <user id>
- **Statuses**: <in progress> / <PR open> / <merged to base> / <done>
- **Automation quirks**: <e.g. which events move statuses, whether it fires on integration merges, delays, which ids it parses from title, body, branch>
- **Link format in PR bodies**: <raw id vs custom id>
- **PR title format**: <e.g. `[<task id>] <title>`>
- **Labels that exist per repo**: <labels, or "none">

### Review

- **Review tool**: <skill or script, absolute path, diff-base argument for stacked PRs>
- **Comment-addressing pass**: <skill name>
- **Attribution policy**: <e.g. no AI attribution in commits, PR bodies or code>

### Stack and verification

- **Dependency install per repo**: <command>
- **Start a per-worktree stack**: <command and project-name rule>
- **Stop a per-worktree stack**: <command; which stacks to keep running>
- **Migrate / seed**: <command>
- **Tests and checks before push**: <per repo>
- **Known timeouts and their global fix**: <e.g. raise a package manager's process timeout in the container>
- **Pre-ship steps**: <regenerated files, lockfiles, docblocks; what to commit and what to discard>
- **Local verification**: <how to run the integration branches together; where screenshots go>
- **Close-out**: <decision capture, docs to update>

### Workers

- **Read-first files**: <absolute path of the workspace CLAUDE.md; product-context files>
- **Files workers must never commit**: <besides .task-brief.md and .orchestrator-answers.md>
- **Protected files the orchestrator writes for workers**: <e.g. env files under a deny rule>
- **Consent gates to check in pre-flight**: <tools that prompt before commits>
- **Permission rules in the orchestrator settings**: <the exact `Bash(...)` rules, with the expanded scripts path>

### Design sign-off

- **Enabled**: <yes / no; which changes need it>
- **Font and design-token paths**: <paths>
- **Themable brand color**: <token names, if the app themes per tenant>
```

## gotchas.md

```markdown
# Gotchas: <project>

Project-specific; generic ones live in the skill's method.

| Symptom | Cause | Fix | Seen |
|---|---|---|---|
| <what you saw> | <why> | <what to do> | <date, run> |
```

## brief-rules/common.md

```markdown
## Project rules (every repo)

- <attribution policy>
- <PR body sections and tracker link format>
- <data policy, e.g. synthetic data only>
```

## brief-rules/repo.md

Name the file after the repo key used in `ids.json`.

```markdown
## <repo> rules

- Checks before push: <commands>
- Tests: <framework, how to run, what is exempt>
- Setup before the first push: <e.g. raise a timeout, run migrations>
- <API contract to paste verbatim into consumer briefs, or where to find it>
- <mockup path and token mapping rule, for UI repos>
```

## runs/README.md

```markdown
# Runs

| Run | Story | Repos | Outcome |
|---|---|---|---|
| `YYYY-MM-DD-<story>/` | <story id and title> | <repos> | <shipped / in progress> |
```

## runs/YYYY-MM-DD-story/README.md

```markdown
# <story id>: orchestration run, YYYY-MM-DD

## Kickoff contract

<the confirmed contract from method §0>

## Integration branches

| Repo | Branch | PR | Ship order |
|---|---|---|---|

## Waves

| Wave | Task | Repo | Worktree | Branch | Terminal | PR | State |
|---|---|---|---|---|---|---|---|

## Decisions made on the user's behalf

- <date time>: <question> → <answer>, because <reason>

## Parked for the user

- <question, options, recommendation>

## Lessons

<also folded into gotchas.md or the profile>
```
