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

### Always-on globally (low/no overhead)
- `rust-analyzer-lsp` — Rust LSP
- `pyright-lsp` — Python LSP (installed via `uv tool install pyright`)
- `typescript-lsp` — TypeScript LSP
- `code-simplifier` — on-demand skill/agent
- `claude-md-management` — on-demand skill
- `claude-code-setup` — on-demand skill
- `skill-creator` — on-demand skill
- `security-guidance` — PreToolUse hook, checks for XSS/injection patterns on every file edit

### Disabled globally (enable per-project)
- `github` — GitHub MCP (30-50 tools, high overhead)
- `svelte@svelte` — Svelte MCP + LSP (MCP overhead not worth it globally)
- `superpowers` — SessionStart hook injects ~800 words every session
- `huggingface-skills` — HuggingFace MCP server

### Enabling a plugin per-project
Add to `.claude/settings.json` at the project root:
```json
{
  "enabledPlugins": {
    "github@claude-plugins-official": true,
    "svelte@svelte": true
  }
}
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
