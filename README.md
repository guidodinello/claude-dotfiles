# claude-dotfiles

Personal Claude Code configuration — agents, skills, hooks, and guidelines synced across machines via symlinks.

## Structure

```
.claude/
  agents/          # Subagents invoked by Claude during tasks
  guidelines/      # Reusable coding guidelines (@-imported into project CLAUDE.md files)
  hooks/           # Lifecycle hooks (PostToolUse, etc.)
  scripts/         # Standalone utility scripts
  skills/          # Slash-command skills (/skill-name)
```

## Quick Reference

| Area | Description | Details |
|---|---|---|
| [Skills](docs/skills.md) | 26 slash-command skills | `/address-pr-comments`, `/code-health`, `/security-audit`, `/db-migration-planner`, etc. |
| [Agents](docs/agents.md) | 6 subagents | audit-finding-verifier, clickup-create-task, quality-checker, slite-sync, etc. |
| [Hooks](docs/hooks.md) | Safety guards + auto-format + status line | Docker volume guard, Wrangler production guard, auto-format.sh, statusline.sh |
| [Guidelines](docs/guidelines.md) | Reusable coding conventions | Python guidelines |

## Setup on a new machine

**Install everything:**

```bash
git clone git@github.com:<you>/claude-dotfiles.git ~/claude-dotfiles
cd ~/claude-dotfiles
bash setup.sh
```

`setup.sh` symlinks every file under `.claude/` into `~/.claude/`, backing up any pre-existing files as `.bak`.

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

Moves the file/directory into the repo and creates file-level symlinks back. The live `~/.claude/` and the repo stay in sync.

### Promote a skill from a project to global

```bash
./promote.sh /path/to/project/.claude/skills/my-skill
./promote.sh ~/.claude/agents/my-agent.md      # also works for ~/.claude/ sources
```

Moves the item into this repo and creates symlinks in `~/.claude/` so it's immediately available globally. If the source was project-local, the original path is left in place with a message telling you it's safe to remove.

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
