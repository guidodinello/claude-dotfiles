# Plugins, LSP & MCP Guide

## How the systems fit together

Claude Code has three distinct systems that are easy to conflate:

### 1. VS Code IDE integration
Enabled automatically when running Claude Code from VS Code. Provides:
- `getDiagnostics` tool — reads errors/warnings directly from VS Code's language servers (Pylance, etc.)
- No extra setup needed; Python diagnostics from Pylance work out of the box

### 2. Claude Code LSP plugins
Independent of VS Code. Provide navigation features (go-to-definition, find-references, hover).
Must be installed separately via `claude plugin install <name>`.
**Token impact: negligible** — background processes, no API overhead.

### 3. MCP plugins
Expose tools to Claude via the Model Context Protocol.
**Token impact: high** — tool definitions are injected into every API request, whether used or not.

---

## Token cost by plugin type

| Type | Always-on cost | Example |
|---|---|---|
| MCP server | High (tool definitions in every request) | github, svelte MCP, huggingface |
| SessionStart hook | High (injected into every session) | superpowers |
| PreToolUse hook | Low (runs per edit, no token cost) | security-guidance |
| LSP plugin | None (background process) | pyright-lsp, rust-analyzer-lsp |
| Skills/agents | None until invoked | code-simplifier, claude-md-management |

**Rule: disable MCP plugins globally. Enable per-project when needed.**

---

## Current global plugin config (~/.claude/settings.json)

Global config is kept to **universal-only** plugins — anything language- or
stack-specific is enabled per-project (see below).

### Always-on globally (universal, low/no overhead)
- `skill-creator` — on-demand skill
- `code-simplifier` — on-demand skill/agent
- `engram` — persistent-memory MCP (kept global by choice; note MCP tool defs
  are the main per-conversation cost)
- `claude-code-setup` — on-demand skill
- `security-guidance` — PreToolUse hook, checks for XSS/injection patterns on every file edit
- `claude-md-management` — on-demand skill
- `code-review` — disabled globally (`false`)

### Enabled per-project (not global)
Language-specific LSPs and stack tools live in the **project's** settings so a
Python project doesn't carry the PHP LSP and vice versa:
- `pyright-lsp` — Python LSP
- `php-lsp` — PHP LSP
- `typescript-lsp` — TypeScript/JS LSP
- `frontend-design` — UI/design helper (frontend projects)

### High-overhead plugins to keep per-project (reference)
These are deliberately **not** enabled globally because their always-on cost is
high — enable them only in the specific projects that need them:
- `github` — GitHub MCP (~30–50 tool definitions injected every request)
- `svelte@svelte` — Svelte MCP + LSP (MCP overhead not worth it globally)
- `superpowers` — SessionStart hook injects ~800 words into every session
- `huggingface-skills` — HuggingFace MCP server

---

## Per-project LSP: the scheme

**Key idea:** Claude Code deep-merges settings across scopes
(`~/.claude/settings.json` → `<project>/.claude/settings.json` →
`<project>/.claude/settings.local.json`). `enabledPlugins` is an object map, so
a project can switch on a plugin that global left off, and it stays isolated to
that project. Verified empirically: enabling `code-review` at project scope
showed `enabled=true` inside the project and `enabled=false` in `$HOME`.

Because project settings live **in the project repo**, they travel with
`git clone`. You configure a project **once, ever** — not once per machine. On a
new PC: clone dotfiles (global) + clone your projects (each carries its own LSP
config). Nothing extra to run.

The official marketplace only needs to be known at user scope — keep
`extraKnownMarketplaces` in `~/.claude/settings.json`. Projects reference plugins
from it without redeclaring the marketplace.

> First time a project enables `typescript-lsp` (not installed by default),
> Claude Code auto-installs it from the official marketplace on session start.

### `project-init` (stack detection)

Run it from this repo against any project — no global install; it mirrors the
other repo scripts (e.g. `promote.sh`) by taking the target path as an argument.
It auto-detects the stack and **deep-merges** into any existing settings file
(won't clobber committed team config):

```bash
cd ~/claude-dotfiles
./project-init /path/to/project              # auto-detect: pyproject/requirements/setup.py/Pipfile→python,
                                             #              composer.json→php, package.json→node
./project-init /path/to/project python       # force a stack
./project-init /path/to/project node --local # write gitignored settings.local.json (team repos)
```

The project directory defaults to the current directory if omitted.

- **Default** → writes committed `.claude/settings.json`, so it travels via
  `git clone`. Best for your own repos.
- **`--local`** → writes `.claude/settings.local.json` (gitignored). Use in team
  repos where you don't want to commit personal plugin prefs. Trade-off: local
  files don't travel with clone, so re-run per machine.
  (Ensure the project's `.gitignore` lists `.claude/settings.local.json`.)

Templates live in [`templates/claude-settings/`](../templates/claude-settings/)
(`python.json`, `php.json`, `node.json`) — edit these to change what each stack enables.

### Enabling any plugin per-project manually
Either add to `.claude/settings.json` at the project root:
```json
{
  "enabledPlugins": {
    "pyright-lsp@claude-plugins-official": true
  }
}
```
…or let the CLI write it for you:
```bash
claude plugin enable pyright-lsp@claude-plugins-official --scope project
```

---

## LSP setup notes

### How Pyright handles virtual environments
Pyright is a standalone analyzer, not a library — install it globally, not in your venv.
It auto-detects `.venv/` in the workspace root. For non-standard locations:
```json
// pyrightconfig.json
{ "venvPath": ".", "venv": ".venv" }
```
Preferred install method: `uv tool install pyright` (permanent, in PATH, isolated).

### svelte-language-server binary quirk
The npm package installs as `svelteserver`, but the plugin expects `svelte-language-server`.
Fix applied: symlink in nodenv bin directory.
```bash
ln -s ~/.nodenv/versions/<ver>/bin/svelteserver ~/.nodenv/versions/<ver>/bin/svelte-language-server
nodenv rehash
```

---

## Diagnosing plugin issues

Check `~/.claude/debug/latest` for startup errors:
```bash
grep -i "lsp\|mcp\|error\|warn" ~/.claude/debug/latest | head -40
```

Key things to look for:
- `Total LSP servers loaded: N` — confirms LSP plugins started
- `Missing environment variables` — MCP plugin needs env var configured
- `Executable not found in $PATH` — LSP binary not installed

---

## Environment variables for MCP plugins

`settings.local.json` only exists at **project scope**, not user scope.
`~/.zshrc` exports are NOT picked up — Claude Code is launched by VS Code, not a terminal.

**Correct place for user-scoped secrets: `~/.claude/settings.json` under `"env"`**
```json
{
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "gho_..."
  }
}
```
The token can be sourced from the `gh` CLI: `gh auth token`.
