# claude-dotfiles

Personal Claude Code configuration — agents, skills, and hooks synced across machines.

## Contents

```
.claude/
  agents/
    quality-checker.md      # QA subagent: runs type-check, linting, tests; returns concise summary
  guidelines/
    python.md               # General Python coding guidelines — import into any project's CLAUDE.md
  hooks/
    auto-format.sh          # PostToolUse hook: auto-formats edited files (stack-agnostic)
  skills/
    conventional-commits/
      SKILL.md              # /conventional-commits — generates granular conventional commits
    qa-check/
      SKILL.md              # /qa-check — triggers quality-checker subagent
```

> **Note:** `quality-checker` and `qa-check` are tailored for a Laravel 12 + React stack (`pnpm`, `sail`). They will silently do nothing on other projects.
> `auto-format.sh` and `conventional-commits` are fully generic and work anywhere.

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

`select.sh` presents an interactive picker (uses `fzf` if available, plain numbered menu otherwise) grouped by category — skills, agents, hooks, guidelines, scripts. Select individual items and only those get symlinked. Useful when you cloned the repo for one specific skill and don't want the rest.

## Adding a new skill/agent/hook

Drop the file somewhere under `~/.claude/`, then:

```bash
cd ~/claude-dotfiles
./add_file.sh ~/.claude/skills/my-skill/SKILL.md
git add .claude/skills/my-skill/SKILL.md
git commit -m "feat: add my-skill"
git push
```

`add_file.sh` moves the file into the repo and creates a symlink back, so your live Claude Code setup and the repo stay in sync automatically.

## Bootstrapping a new Python project

Add one line to the new project's `CLAUDE.md` to pull in the shared Python guidelines:

```markdown
@/home/guido/.claude/guidelines/python.md

## Project-specific notes
...
```

Claude Code's `@path` import loads the file at the start of every session, so the
guidelines stay in sync with the dotfiles repo without copying anything. Add
project-specific overrides or additions after the import.

To add guidelines for another stack (JS, Rust, etc.) just create
`.claude/guidelines/<stack>.md` in this repo — it will be symlinked automatically by
`setup.sh`.

## Docs

- [Recommended plugins](docs/recommended-plugins.md) — curated MCP, LSP, and skill/agent plugins worth having
- [Plugins, LSP & MCP guide](docs/plugins-lsp-mcp-guide.md) — token cost model, per-project enabling, env vars
- [Claude usage insights](docs/claude-usage-insights.md) — token/cost patterns and optimization notes

## Wiring the auto-format hook

The hook detects the stack automatically using local binaries (`node_modules/.bin`, `vendor/bin`) — no configuration needed per project. To enable it globally, add to `~/.claude/settings.json`:

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
