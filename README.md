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

## Skills

| Skill | Description |
|---|---|
| `/clean-permissions` | Generalizes overly-specific Bash permission rules in settings files |
| `/clickup-item-generator` | Creates Bug/Improvement/Task tickets in ClickUp for the active project |
| `/code-health` | Codebase readiness audit: type safety, dead code, test coverage, complexity, deps |
| `/conventional-commits` | Generates granular conventional commits from staged changes |
| `/db-migration-planner` | Plans a database migration between providers with schema and data steps |
| `/db-scalability-audit` | Database scalability & architecture audit with provider-specific limits |
| `/figma-to-tailwind` | Implements UI components from Figma designs using Tailwind 4 + tailwind-variants |
| `/git-brag` | Finds your commits on a path, formatted for perf-review docs |
| `/hipaa-audit` | HIPAA Security Rule compliance audit for healthcare codebases |
| `/meta-skill-db-scalability-audit-improver` | Refreshes provider limits and anti-patterns in the db-scalability-audit skill |
| `/meta-skill-hipaa-audit-improver` | Refreshes regulatory guidance and enforcement cases in the hipaa-audit skill |
| `/permissions-audit` | Comprehensive authorization audit across roles, permissions, and auth logic |
| `/qa-check` | Runs type-check, linting, and tests via the quality-checker subagent (Laravel + React) |
| `/security-audit` | Application security audit covering OWASP Top 10 vulnerability patterns |
| `/ticket-refinement` | Writes and refines subtasks for software tickets (endpoints, components, APIs) |
| `/token-report` | Token usage report from Claude Code stats |
| `/writing-react-effects` | Reviews/writes React components to eliminate unnecessary useEffect usage |

> **Stack-specific:** `/qa-check` is tailored for a Laravel 12 + React stack (`pnpm`, `sail`) and will do nothing on other projects. All other skills are generic.

## Agents

| Agent | Description |
|---|---|
| `quality-checker` | Runs the full QA pipeline and returns a concise summary of issues |
| `slite-sync` | Syncs a local Markdown file to a Slite document |
| `stats-analyzer` | Analyzes `stats-cache.json` and `history.jsonl` for token/cost usage reports |

## Guidelines

| File | Use |
|---|---|
| `guidelines/python.md` | Python coding guidelines — exception handling, async, generators |

Import into any project's `CLAUDE.md` with `@~/.claude/guidelines/python.md`. The file is loaded fresh each session, so it stays in sync with this repo without copying.

## Hooks

**`auto-format.sh`** — `PostToolUse` hook that auto-formats files after edits. Detects the project stack automatically via local binaries (`node_modules/.bin`, `vendor/bin`). Supports ESLint/Prettier (JS/TS/CSS) and PHP-CS-Fixer/Pint. Always exits 0 so formatter failures never block Claude.

Wire it globally in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "bash ~/.claude/hooks/auto-format.sh" }]
      }
    ]
  }
}
```

Override per-project by creating `.claude/hooks/auto-format.sh` in the project root.

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

## Docs

- [Recommended plugins](docs/recommended-plugins.md) — curated MCP, LSP, and skill/agent plugins worth having
- [Plugins, LSP & MCP guide](docs/plugins-lsp-mcp-guide.md) — token cost model, per-project enabling, env vars
- [Claude usage insights](docs/claude-usage-insights.md) — token/cost patterns and optimization notes
