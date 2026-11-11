---
name: worktree-bootstrap
description: "Trigger: worktree bootstrap, Orca setup script, archive script, new worktree not ready, isolate worktree ports or compose project, link workspace CLAUDE.md into worktrees. Write one thin setup script per repo that sources a shared helper library, so every new worktree comes up isolated (own compose project and host ports), with env files copied, deps installed and the workspace context linked."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when a workspace's repos need their worktrees to come up ready on creation: writing or fixing the per-repo "Setup Script" or "Archive Script" that Orca (a worktree manager) runs, isolating a worktree's docker compose stack and ports, copying env files into worktrees, or making Claude Code sessions in worktrees see the workspace `CLAUDE.md` and private notes. Also load before changing `lib.sh`.

Not for running the app in the main checkout, and not for orchestrating workers in worktrees (that is `orca-orchestration`).

The method and the helpers live here. Everything project-specific (repo names, compose prefix, port bases, services, install and migration commands) lives in the per-repo scripts, which stay in the project's private notes folder. Never put project-specific content in this skill.

## How the pieces connect

```text
Orca (creates <worktrees>/<name>, sets $ORCA_WORKTREE_PATH)
  │ runs the repo's Setup Script field: bash <workspace>/my-dev-things/setup/bootstrap-worktree-<repo>.sh
  ▼
per-repo script (project constants, stack-specific steps)
  │ sources
  ▼
~/.claude/skills/worktree-bootstrap/lib.sh  ──symlink (dotfiles sync.sh)──▶  dotfiles checkout
  │ reads/links
  ▼
<workspace>/<repo> (main checkout: env files)   <workspace>/CLAUDE.md   <workspace>/my-dev-things/
```

- A workspace is a folder whose subdirectories are the repos' main checkouts. `workspace_root` is the main checkout's parent; set `WORKTREE_WORKSPACE_ROOT` when that is not true.
- Projects **source** the installed `lib.sh`, never copy it, so a fix reaches every project at once. The dotfiles `sync.sh` installs per-file symlinks into `~/.claude/skills/`, so a new file in this skill appears there only after `./sync.sh` is re-run.
- `WORKTREE_BOOTSTRAP_LIB` overrides the lib path (used by the self-check and when testing an unmerged lib).

## Hard Rules

- **Safe to re-run.** Every step checks before acting: copy only when missing, isolate ports only when the env file is not already isolated, install only when deps are absent, append an exclude pattern only once. Re-running is how an old worktree picks up a fix.
- **Never print env values.** Copy env files whole and edit single keys with `set_env_key` / `delete_env_key`. `get_env_key` prints, so call it only for keys the bootstrap owns (ports, project names, local URLs). Report key names, never values.
- **Refuse the main checkout.** `require_worktree` dies there; teardown warns and exits 0. The main checkout's compose project is never touched (`assert_worktree_project`).
- **Names and ports come from the worktree name.** Compose project `<prefix><slug(name)>`, readable in `docker ps`. Port = base + offset, offset 1..899 from the name, walking forward only past ports already listening. Space bases at least 1000 apart. Record the offset in the env file and have sibling repos read it instead of recomputing.
- **Schedulers and heavy optional services stay off in worktrees.** A worktree runs with credentials copied from the main checkout, so a cron/scheduler service would call external systems unattended. Put such services behind compose profiles in a locally written override.
- **Nothing tracked is edited.** Local files (compose override, links) are hidden through the common `.git/info/exclude`, never `.gitignore`. A tracked file that local tooling keeps rewriting gets `skip_worktree`, never a commit.
- **Link the workspace context.** `link_workspace_context` links the workspace `CLAUDE.md` as `CLAUDE.local.md` (Claude Code loads it) and the notes folder under a **dot name** (`.my-dev-things`). A plain-name link was followed by a frontend's `tsc`, whose `include` of `**/*.ts` compiled the notes' scripts; the dot name is skipped by such globs. Inside a worktree, refer to the notes as `.my-dev-things/...`.
- **Stacks with containers or volumes get a teardown script** in Orca's Archive Script field. It always exits 0: cleanup must never block removing a worktree.
- **Stack-specific logic stays in the per-repo script.** Add to `lib.sh` only small helpers that two or more stacks need, and never change an existing helper's signature: every project sources the same file.

## Decision Gates

| Condition | Action |
|---|---|
| `lib.sh` missing at the installed path | The script exits 1 with a message. Run `./sync.sh` in the dotfiles checkout |
| Workspace `CLAUDE.md` missing | Die: a worktree without it loses every workspace rule. Fix the layout or set `WORKTREE_WORKSPACE_ROOT`. A missing notes folder only warns |
| Env file missing in the main checkout | Required: die with a message. Optional (e.g. E2E credentials): warn, create nothing, so the tool fails with its own message |
| Repo publishes host ports or runs containers | Compose example + teardown script |
| Repo is a frontend that talks to a backend repo | Vite example: pair with the backend worktree of the same name, else the main API |
| Repo needs no runtime (infra, docs) | Links-only example |
| A tracked file must change for local runs | `skip_worktree` plus a local rewrite; never commit it |
| An override file name is already tracked | Stop and adapt; do not overwrite it |
| `lib.sh` or an example changed | Run the self-check before committing |

## Procedure: a new project

1. **Map the workspace.** List the main checkouts (`<workspace>/*/.git`) and each repo's role.
2. **Per repo, find from the code:** compose files and which services publish host ports (hardcoded or env-driven); scheduler, cron and heavy optional services; the gitignored env files the app needs and their `.example`; the runtime pin (`.nvmrc`, `packageManager`, `composer.json`) and install command; migrations; a health URL; and, for a frontend, the env key that holds the API URL.
3. **Choose the project constants:** a short compose prefix ending in `-`, one port base per published port, 1000 apart and clear of ports the main checkout uses.
4. **Write one script per repo** into the project's private notes folder (e.g. `<workspace>/my-dev-things/setup/bootstrap-worktree-<repo>.sh`), starting from the closest example. Keep the lib-loading block as it is. See [references/stack-notes.md](references/stack-notes.md) for stack specifics (Laravel Sail, composer hooks, env from template).
5. **Test it on a real worktree** before wiring it: `git -C <workspace>/<repo> worktree add --detach <scratch>/<name> HEAD`, run `ORCA_WORKTREE_PATH=<scratch>/<name> bash <script>` twice, check `git -C <scratch>/<name> status --porcelain` is empty and the second run changes nothing. Tear down what it started, then `git worktree remove --force`.
6. **Give the user the exact lines to paste** in Orca (Settings, Git & Source Control, per repo), with absolute paths:
   - Setup Script: `bash <workspace>/my-dev-things/setup/bootstrap-worktree-<repo>.sh`
   - Archive Script (stacks with containers only): `bash <workspace>/my-dev-things/setup/teardown-worktree-<repo>.sh`
7. **Index the scripts** in the notes folder's README, with the paste lines.

Orca behavior to account for: the Archive Script runs only on `orca worktree rm --run-hooks`; the Setup Script can still be running after `orca worktree create` returns, so check its result (env file, `node_modules`, `docker ps`) before launching work in a new worktree.

## Changing lib.sh

1. Edit it in a dotfiles worktree, never in `~/.claude/skills/` (those are symlinks into the main dotfiles checkout).
2. Run the self-check, which tests the copy next to it, not the installed one:

   ```bash
   bash <dotfiles-worktree>/.claude/skills/worktree-bootstrap/scripts/self-check.sh
   ```

   It runs `bash -n` with `/bin/bash` (3.2 on macOS) and the PATH `bash` over the lib, the examples and itself; unit-checks the env and naming helpers; then builds a throwaway workspace and repo under a temp dir, adds a detached worktree outside the workspace, runs the links-only example twice and verifies both links resolve, `git status --porcelain` is empty, each exclude pattern appears once, and the main checkout is refused. It also loads the lib through an installed-style `$HOME/.claude/skills/worktree-bootstrap/lib.sh` symlink without the override, checks the clear failure when the lib is missing, and checks the run dies without a workspace `CLAUDE.md`. It removes the worktree and the temp dir on exit.
3. It reaches projects only once it is in the main dotfiles checkout: after the merge, `git pull` there (the `~/.claude` symlinks point into it), and re-run `./sync.sh` when the change added a file.

## Lib Reference

| Helper | Use |
|---|---|
| `worktree_dir` | `$ORCA_WORKTREE_PATH` or `$PWD`, as the repo toplevel |
| `main_checkout <dir>` / `is_main_checkout <dir>` | Resolve or detect the main checkout |
| `require_worktree <dir> [repo-name]` | Die on the main checkout or a worktree of another repo |
| `workspace_root <main>` | Main checkout's parent, or `$WORKTREE_WORKSPACE_ROOT` |
| `paired_worktree <main> <sibling-repo> <name> [file]` | Sibling repo's worktree with the same name |
| `compose_project_name <prefix> <name>` / `assert_worktree_project <project> <prefix> [main-project]` | Readable project name; refuse anything else |
| `port_offset <name>` / `pick_free_offset <name> <base>...` | Stable offset; first free one from it |
| `get_env_key` / `has_env_key` / `set_env_key` / `delete_env_key` | Single-key env edits; values stay literal |
| `fill_missing_env_keys <env> <example>` | Append keys the example has and the env lacks |
| `copy_from_main <main> <dir> <path> [--optional]` | Copy without reading, never overwrite |
| `is_tracked` / `ensure_git_exclude` / `skip_worktree` | Keep local state out of commits |
| `link_excluded <dir> <target> <name>` / `link_workspace_context <dir> <ws> [notes]` | Excluded symlinks; never over a real or tracked file |
| `use_repo_node <dir>` | `.nvmrc` via nvm, corepack prompts off |
| `wait_for_docker [timeout]` / `wait_for_http <url> [timeout] [code]` | Readiness waits |
| `log` / `warn` / `die` / `require_cmd` | Output and preconditions |

## Output Contract

Reply in the conversation language. For a new project: the scripts written (paths), what each does per repo, the test run's output, and the exact Orca paste lines. For a lib change: the self-check output and whether any helper's behavior changed for existing projects.

## References

- [lib.sh](lib.sh): the helpers.
- [examples/](examples/): `bootstrap-compose-backend.sh`, `teardown-compose-backend.sh`, `bootstrap-vite-frontend.sh`, `bootstrap-playwright.sh`, `bootstrap-links-only.sh`.
- [scripts/self-check.sh](scripts/self-check.sh): run after any lib or example change.
- [references/stack-notes.md](references/stack-notes.md): stack-specific lessons.
