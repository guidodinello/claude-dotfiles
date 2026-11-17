# claude-dotfiles

Personal Claude Code configuration — agents, skills, hooks, and guidelines synced across machines via symlinks.

## Structure

```
.claude/
  agents/          # Subagents invoked by Claude during tasks
  rules/           # Path-scoped guidelines (paths: frontmatter) — load on demand
  guidelines/      # Always-on guidelines (@-imported into CLAUDE.md files)
  hooks/           # Lifecycle hooks (PostToolUse, etc.)
  scripts/         # Standalone utility scripts
  skills/          # Slash-command skills (/skill-name)

sync.sh              # this repo → ~/.claude/ (symlinks)
select.sh            # same, but pick individual items interactively
add_file.sh          # absorb a file already in ~/.claude/ into this repo
promote.sh           # a project → this repo (adopt a file globally)
push-guidelines.sh   # this repo → projects that keep committed guideline copies
project-init         # scaffold per-project LSP/plugin settings by stack
lib/link.sh          # shared by the scripts above: config dirs, symlink + backup, prune
tests/               # tests for the scripts and hooks (see Tests)
```

Root-level scripts are run from the checkout (`./sync.sh`) — they are not
symlinked into `~`.

## Quick Reference

| Area | Description | Details |
|---|---|---|
| [Skills](docs/skills.md) | Slash-command skills | `/address-pr-comments`, `/code-health`, `/security-audit`, `/db-migration-planner`, etc. |
| [Agents](docs/agents.md) | Subagents | audit-finding-verifier, quality-checker, slite-sync, stats-analyzer |
| [Hooks](docs/hooks.md) | Safety guards + JSON lint + status line | guard-bash.sh (Docker volumes, Wrangler production), json-lint.sh, statusline.sh. auto-format.sh is opt-in per project |
| [Rules & guidelines](docs/guidelines.md) | Reusable coding conventions | **Rules** (path-scoped, auto-load): python, php, docker, ci, database. **Guidelines** (always-on): reasoning-discipline, debugging-patterns, react-native, tools/* |

Path-scoped rules in `~/.claude/rules/` apply to **every project on the machine with no
per-project wiring** — a `.py` edit pulls in `python.md` wherever you are. Full rationale,
the two consumption models, the per-folder convention and the promote-then-genericize
checklist: [The guideline system](docs/guideline-system.md).

### The three sync directions

Guidelines and other `.claude/` content move in three directions. Getting these
straight matters — the wrong one silently discards work:

| Direction | Script | When |
|---|---|---|
| this repo → `~/.claude/` | `sync.sh` | after `git pull`, or a new machine |
| a project → this repo | `promote.sh` | a project-local file is good enough to go global |
| this repo → projects | `push-guidelines.sh` | refresh the committed copies repos carry |

**Edited a guideline inside a project? `promote.sh` first, then `push-guidelines.sh`.**
Pushing first overwrites your edit with the older global version.

## Setup on a new machine

**Install everything:**

```bash
git clone git@github.com:<you>/claude-dotfiles.git ~/claude-dotfiles
cd ~/claude-dotfiles
bash sync.sh
```

`sync.sh` symlinks every file under `.claude/` into `~/.claude/`, backing up any pre-existing files as `.bak`. Safe to re-run any time — e.g. after `git pull` — to pick up new or updated skills/agents/hooks.

Each run also cleans up after itself:

- **Dangling links are pruned.** A symlink in a config dir that points into this repo at a file that no longer exists (deleted or moved here) is removed. Links pointing anywhere else are left alone.
- **Old settings backups are trimmed.** A run that changes `settings.json` saves the previous one as `settings.json.bak-<timestamp>`; only the newest 3 of those are kept. Backups with any other name (`.bak`, `.bak-engram`, ...) are never deleted.

**Install only what you need:**

```bash
bash select.sh
```

`select.sh` presents an interactive picker (uses `fzf` if available, plain numbered menu otherwise) grouped by category. Select individual items and only those get symlinked.

## Managing the repo

### Absorb a file already in `~/.claude/`

```bash
./add_file.sh ~/.claude/agents/my-agent.md
./add_file.sh ~/.claude/skills/my-skill        # directories work too
```

Moves the file/directory into the repo and creates file-level symlinks back, in `~/.claude/` and in every `~/.claude-*` profile. The live config dirs and the repo stay in sync.

### Promote a skill from a project to global

```bash
./promote.sh /path/to/project/.claude/skills/my-skill
./promote.sh ~/.claude/agents/my-agent.md      # also works for ~/.claude/ sources
```

Moves the item into this repo and creates symlinks in `~/.claude/` (and every `~/.claude-*` profile) so it's immediately available globally. If the source was project-local, the original path is left in place with a message telling you it's safe to remove.

Add `--delete-original` to skip the reminder (the `mv` already removed it):

```bash
./promote.sh --delete-original /path/to/project/.claude/skills/my-skill
```

After either script, commit the new files:

```bash
git add .claude/<rel-path>
git commit -m "feat: add my-skill"
git push
```

### Push guidelines into a project

Most projects need no wiring at all: `~/.claude/rules/` is symlinked back here, so a
path-scoped rule fires machine-wide and can never drift. But a repo that must be readable
from a remote Claude web session or another machine has no `~/.claude/`, and symlinks
don't survive `git clone` — those repos commit their own copy, and copies drift. This
pushes the repo master back over them:

```bash
cd ~/claude-dotfiles
./push-guidelines.sh                  # dry run over every opted-in project
./push-guidelines.sh --apply          # actually write
./push-guidelines.sh /path/to/project # one project only
```

A project opts in simply by having a `.claude/rules/`, `.claude/guidelines/`,
or `.claude/skills/` directory; all three are synced independently. Two rules
keep it safe:

- **Only files the project already has are refreshed.** Adopting a new guideline
  stays a deliberate `cp`, so a Node repo never wakes up owning `php.md`, and a
  project's own skills (e.g. fitted's `feature-workflow`) are never pushed at.
- **Nothing is ever deleted**, so project-specific files living alongside the
  shared ones survive untouched. This is how a promoted skill can stay in both
  places: the repo copy is the source of truth, fitted's committed copy gets
  refreshed on every push, and fitted's own project-specific skills are left
  alone.

Dry run is the default; `--apply` overwrites local edits without prompting. Then
commit the updated copies in each project repo.

### Enable per-project LSP (`project-init`)

Language-specific LSP plugins (pyright, php, typescript) are enabled per-project,
not globally, so each project only loads the LSP it needs. Project settings live
in the project repo, so they travel with `git clone` — configure a project once,
ever, not once per machine.

Run it from this repo (like the other scripts — no global install needed),
passing the target project directory:

```bash
cd ~/claude-dotfiles
./project-init /path/to/project              # auto-detect stack (python/php/node)
./project-init /path/to/project python       # force a stack
./project-init /path/to/project node --local # write gitignored settings.local.json (team repos)
```

The project directory defaults to the current directory if omitted. It deep-merges
into any existing settings without clobbering. Stack templates live in
`templates/claude-settings/`. See [Plugins, LSP & MCP guide](docs/plugins-lsp-mcp-guide.md#per-project-lsp-the-scheme) for the full scheme.

## Tests

```bash
python3 -m unittest discover -s tests          # sync.sh, select.sh, add_file.sh, promote.sh, guard-bash.sh
shellcheck -x -S warning $(git ls-files '*.sh') project-init
```

The script tests run against a throwaway copy of the scripts and a throwaway `HOME`, so they never touch the real `~/.claude`. Skill scripts keep their own `test_*.py` next to them; run those from their directory (`python3 -m unittest discover -p 'test_*.py'`). CI runs all three on every PR (`.github/workflows/tests.yml`).

## Credits

Some skills in this repo originate from external authors and are vendored here with attribution:

| Skill | Author | Source |
|---|---|---|
| `/improve-codebase-architecture` † | [Matt Pocock](https://github.com/mattpocock) | [mattpocock/skills](https://github.com/mattpocock/skills) |

Skills are vendored into `.claude/skills/` so they work with Claude Code's slash-command system. The originals are installable via `npx skills add mattpocock/skills`.

## Docs

- [Recommended plugins](docs/recommended-plugins.md) — curated MCP, LSP, and skill/agent plugins worth having
- [Plugins, LSP & MCP guide](docs/plugins-lsp-mcp-guide.md) — token cost model, per-project enabling, env vars
- [Claude usage insights](docs/claude-usage-insights.md) — token/cost patterns and optimization notes
