---
name: release-sim
description: "Trigger: release sim, simulate release, test migration/backfill against prod-like data, will this migration break prod. Simulate a release locally (prod ref → next ref, optionally a fix PR) with synthetic data shapes to catch bugs that only appear when existing data meets new migrations."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when the user wants to simulate a release locally, check a migration or backfill against prod-shaped data, or verify that a fix PR resolves a release-only bug. Not for unit tests, deploys, or anything that needs real data.

The method lives here. Everything project-specific (refs, commands, ports, data shapes, lessons) lives in a per-project docs folder that this skill reads, writes on first run, and updates after every run. Never put project-specific content in this skill.

## Hard Rules

- **Synthetic data only.** Never connect to, dump, or copy a prod or dev database. Never use real names, emails, or identifiers. This is a healthcare org rule (PHI): when in doubt, treat it as PHI and do not use it.
- **Local only.** Never push, never deploy, never touch product branches. The sim worktree is detached.
- **Own stack.** Use a dedicated compose project name (`relsim-<change-slug>`) and override every forwarded host port (app, DB, Redis, mail UI, ...) so the sim never collides with a running stack.
- **Never stop what you did not start.** Do not `down`, stop, or reuse a compose project the skill did not create. Stop only its own stack at the end, even on failure.
- **Refs are SHAs.** Resolve every tag/branch with `git rev-parse` at run start and quote full SHAs in reports. A later release can move `main` past the bug you want to reproduce.
- **Scoped writes.** Write only inside the resolved docs folder and the sim worktree.

## Decision Gates

| Condition | Action |
|---|---|
| Docs folder missing | Bootstrap mode |
| Docs folder present | Run mode |
| Data-shape list for the change is empty | **Refuse to run.** Shapes are the whole value |
| `git diff --name-only <prod>..<next> -- <migrations path>` is empty | Advise skipping; proceed only if the user insists |
| Commits in `git log <next>..<prod>` or open back-merge PRs | Stop and ask: the simulation's meaning changes |
| `gh` fails during the hotfix check | Continue with the `git log` check only; add a warning to the run doc |
| A profile port is already bound (`lsof -iTCP -sTCP:LISTEN`, `docker ps`) | Pick a free port, record it in the run doc; update the profile only if the user confirms |

## Docs Folder Location

First match wins:

1. An explicit path argument.
2. `<root>/my-dev-things/release-sim/` when `<root>/my-dev-things/` exists. `<root>` is `git rev-parse --show-toplevel` of the **session cwd**, or the cwd itself when it is not inside a git repo (a multi-repo workspace root). Do not use the product repo's root.
3. Otherwise ask the user for a path before creating anything.

Do not assume whether `my-dev-things/` is committed or gitignored. The profile names which product repo(s) under the workspace get the sim worktree.

## Execution Steps

### Bootstrap (folder missing)

1. Investigate: stack, compose files and their forwarded-port env vars, seeders, migrations path, branch model (from git and CI/deploy config), and how data records get created (tinker/REPL script, seeder class, SQL against the sim DB only).
2. Ask the user, one question at a time, what code cannot tell: which ref prod runs and how to find it, the next-release ref, which data shapes matter.
3. Check the default worktree path (sibling of the product repo) does not land inside any tracked tree: `git status` of the enclosing repo must not show it.
4. Write the folder from [references/docs-template.md](references/docs-template.md), show it, and wait for confirmation before the first run.

### Run (folder present)

1. Read the folder. Ask for the change under test and its data shapes; apply the gates above.
2. Follow [references/method.md](references/method.md): hotfix check, detached worktree at the prod SHA with its own project name and port overrides, fresh DB (migrate + seed), create the shapes, move to the next-release SHA and migrate as a deploy would, optionally move to the PR head and migrate again, re-run for idempotency, report, tear down.
3. Write `runs/YYYY-MM-DD-<change>.md`.
4. Fold every new lesson and shape-creation snippet back into `data-shapes.md` and, if the profile changed, `README.md`.

## Output Contract

Reply in the conversation language: the run doc path, then the before/after table per data shape (release without fix, release with fix, re-run), the refs as SHAs, any warnings, and the lessons added.

## References

- [references/method.md](references/method.md) — the step-by-step procedure with generic commands and a worked data-shape-gap example.
- [references/docs-template.md](references/docs-template.md) — templates for the per-project docs folder.
