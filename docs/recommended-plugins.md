# Recommended Plugins

Opinionated list of plugins worth having for a solid Claude Code setup, organized by type and token cost. See [plugins-lsp-mcp-guide.md](plugins-lsp-mcp-guide.md) for how to install and enable them.

---

## LSP Plugins

No token cost — these run as background processes and don't touch the API. Safe to enable globally.

**`pyright-lsp`** — Python type checking and diagnostics. Install via `uv tool install pyright` (not in a venv — it's a standalone analyzer). Auto-detects `.venv/` in the workspace root.

**`rust-analyzer-lsp`** — Rust LSP. Provides go-to-definition, find-references, and inline diagnostics for Rust projects.

**`typescript-lsp`** — TypeScript/JavaScript LSP. Useful even on JS-only projects for type inference from `.d.ts` files.

**`svelte-lsp`** (part of `svelte@svelte`) — Svelte language server. Note: the npm package installs as `svelteserver` but the plugin expects `svelte-language-server` — requires a symlink fix. See the guide doc.

---

## MCP Plugins

High token cost — tool definitions are injected into every API request. Disable globally; enable per-project only when actively using them.

**`github` (`github@claude-plugins-official`)** — Full GitHub integration: issues, PRs, code search, branch management. ~30-50 tools. Enable for projects where you're doing regular GitHub work. Requires `GITHUB_PERSONAL_ACCESS_TOKEN` in `~/.claude/settings.json`.

**`svelte@svelte`** — Svelte 5 documentation lookup, code validation, and playground links. Enable for Svelte projects. Bundles both MCP and LSP.

**`superpowers`** — Suite of process skills (brainstorming, debugging, TDD, planning, code review). Injects ~800 words on every session start via a SessionStart hook — non-trivial overhead. I enable this globally because the workflow discipline is worth it, but it's a personal call.

**`huggingface-skills`** — HuggingFace Hub operations, model training, dataset management, Gradio UIs. Enable for ML/AI projects.

---

## Skills & Agents

No cost until invoked. Safe to enable globally.

**`code-simplifier`** — Reviews recently changed code for clarity, consistency, and redundancy. Invoke after a feature is done to clean up without over-engineering.

**`claude-md-management`** — Audits and improves `CLAUDE.md` files. Useful when setting up a new project or after significant refactors that make the existing CLAUDE.md stale.

**`claude-code-setup`** — Analyzes a codebase and recommends Claude Code automations (hooks, subagents, skills, MCP servers). Good first step when onboarding a new project.

**`skill-creator`** — Creates, modifies, and benchmarks skills. Use when you want to formalize a workflow into a repeatable skill.

**`security-guidance`** — PreToolUse hook that checks for XSS, injection, and other OWASP patterns on every file edit. Low overhead since it runs locally with no API cost.
