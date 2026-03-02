# claude-dotfiles

Personal Claude Code configuration — agents, skills, and hooks synced across machines.

## Contents

```
.claude/
  agents/
    quality-checker.md      # QA subagent: runs type-check, linting, tests; returns concise summary
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

```bash
git clone git@github.com:<you>/claude-dotfiles.git ~/claude-dotfiles
cd ~/claude-dotfiles
bash setup.sh
```

`setup.sh` symlinks every file under `.claude/` into `~/.claude/`, backing up any pre-existing files as `.bak`.

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
