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
**Token impact: medium to high.** With tool search on (the current default), full tool
schemas are deferred until used. What every session still pays for each connected server is
its **instructions block** plus **one line per tool name** in the deferred-tools list. A
70-tool server (Sentry, ClickUp) is 70 lines in every session, used or not.

---

## Token cost by plugin type

| Type | Always-on cost | Example |
|---|---|---|
| MCP server | Medium–high (instructions + one line per tool name) | github, svelte MCP, huggingface |
| SessionStart hook | High (injected into every session) | superpowers |
| PreToolUse hook | Low (runs per edit, no token cost) | security-guidance |
| LSP plugin | None (background process) | pyright-lsp, rust-analyzer-lsp |
| Skills/agents | None until invoked | code-simplifier, claude-md-management |

**Rule: disable MCP plugins globally. Enable per-project when needed.**

---

## Global plugin config (~/.claude/settings.json)

Global config is kept to **universal-only** plugins — anything language- or
stack-specific is enabled per-project (see below).

`enabledPlugins` is not tracked in this repo. `sync.sh` lists it in `LOCAL_KEYS`, so
each config dir keeps its own toggles. Read the live state there:

```bash
jq '.enabledPlugins' ~/.claude/settings.json
```

Plugins that are global by design:
- `engram` — persistent-memory MCP. Load it **only** as the plugin: a second copy in
  `~/.claude.json` doubles its tool names and instructions (see
  [MCP servers](#mcp-servers-global-vs-per-project)).
- `aws-core` — AWS MCP plus skills; almost every Light-it project runs on AWS.
- `security-guidance` — PreToolUse hook, checks for XSS/injection patterns on every file edit.

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

## MCP servers: global vs per project

MCP servers come from three places, and each is scoped differently:

| Source | Where it lives | Tracked in this repo? | How to scope it |
|---|---|---|---|
| Plugin MCPs (`engram`, `aws-core`) | `enabledPlugins` in `~/.claude/settings.json` and project settings | **No** (`LOCAL_KEYS` in `sync.sh`) | `true`/`false` per settings scope |
| Standalone MCPs (`context7`, `railway`, `linear`) | `~/.claude.json` | **No** | `claude mcp add -s user` (global) or `-s local` (one project path) |
| claude.ai connectors (ClickUp, Slack, ...) | Your claude.ai account | No | Opt-out only: disable per project in `/mcp` |

### The global set

Global because they are used in every Light-it workspace:
- Plugins: `engram`, `aws-core` (almost every Light-it project is hosted on AWS; the
  plugin also lists ~30 skills in every session)
- Standalone: `context7` (2 tools, live library docs)
- claude.ai: ClickUp, Slite, Slack, Sentry, Google Drive, Google Sheets, Claude Docs

Everything else is per project: `railway` (`-s local` in build101), `linear`
(`-s local` in allswell-workspace).

### Gotchas

- **`-s local` is tied to one path.** Orca worktrees of the same repo are different
  paths and don't get the server. If worktrees need it, put it in the repo's
  `.mcp.json` instead.
- **claude.ai connectors are opt-out.** Every project gets every connector in your
  claude.ai "Yours" list. Disabling one in `/mcp` writes it to
  `projects[<path>].disabledMcpServers` in `~/.claude.json`.
- **Unauthenticated connectors still cost tokens.** A connector you never connected
  shows as "needs authentication" and adds two tool names (`authenticate`,
  `complete_authentication`) to every session. Cheap, but not zero.
- **Check for duplicates.** The same server added as a plugin and in `~/.claude.json`
  loads twice. `/mcp` lists both.
- **The AWS MCP uses the default credential chain.** Set `AWS_PROFILE` in the
  workspace's `.claude/settings.local.json` `env` so it uses that client's profile, not
  `[default]`. A `-32602 Invalid request parameters` on connect usually means the SSO
  or `aws login` session expired: re-run `aws sso login --sso-session <name>`.

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

Debug logs are only written in debug mode; without it, `~/.claude/debug/latest` can be a
dangling symlink. Start from the project directory, since project settings (such as
`env`) apply:

```bash
claude mcp list                    # health-checks every server: ✔ Connected / ✘ Failed to connect
claude --debug=mcp --debug-file /path/to/mcp-debug.log mcp list
grep -i "error\|failed" /path/to/mcp-debug.log | head -40
```

The debug log includes each server's stderr, which is where the real cause shows up: a
bare `-32602: Invalid request parameters` in `/mcp` hid an expired AWS SSO token. For
an LSP or a whole session, use `claude --debug --debug-file <path>`.

Key things to look for:
- `Total LSP servers loaded: N` — confirms LSP plugins started
- `Missing environment variables` — MCP plugin needs env var configured
- `Executable not found in $PATH` — LSP binary not installed

---

## Settings scope: what actually persists where

Claude Code resolves settings in this precedence order: Managed (enterprise) > CLI args >
Project **Local** (`.claude/settings.local.json`) > Project (`.claude/settings.json`) > User
(`~/.claude/settings.json`). **There is no user-scope local/gitignored tier** —
`settings.local.json` is only ever resolved relative to a project's git repo root. A file at
`~/.claude/settings.local.json` is not a recognized source and is silently ignored (verified
against Anthropic's settings docs after we mistakenly relied on it — see git history on this
file for the correction).

Practical consequence: there's no clean way to have "shared baseline, but this machine gets
its own untracked exceptions" for anything in `~/.claude/settings.json` (skills, plugins,
env vars, etc.). Two real options if a machine needs to diverge from the committed baseline:

1. **Edit `~/.claude/settings.json` directly.** It is not a symlink: `sync.sh` generates it
   by merging `settings.base.json` with the keys Claude Code writes at runtime. Edits to
   `LOCAL_KEYS` (`autoMode`, `enabledPlugins`, `outputStyle`) survive a re-sync, and so do
   entries added to `hooks` and to the `permissions` lists (both are unioned with the live
   file). Any other key, such as `env`, is rebuilt from `settings.base.json` on the next
   `./sync.sh`, so put those in the base instead.
2. **Don't persist it — use the session-scoped skill picker / `claude plugin enable --scope
   local` for that one session.** Appropriate when the divergence is truly one-off rather than
   a standing per-machine preference.

There is no third option (no per-user gitignored file, no env-var-driven settings path for
this). Per-**project** local settings (`.claude/settings.local.json` inside a project repo)
work exactly as documented and are unaffected by this — see `project-init --local` above.

## Environment variables for MCP plugins

Never put secrets in the `env` of `~/.claude/settings.json`. `env` is not in
`LOCAL_KEYS`, so the next `./sync.sh` rebuilds it from `settings.base.json` and drops
anything added by hand. Putting them in `settings.base.json` instead commits them to
this repo.

Where each kind of value goes:

| Value | Place | Tracked? |
|---|---|---|
| Secret for a standalone MCP | `claude mcp add <name> -s user -e KEY=value -- <cmd>` (stored in `~/.claude.json`) | No |
| Per-project, non-secret (e.g. `AWS_PROFILE`) | `env` in `<project>/.claude/settings.local.json` | No, if the project gitignores it |
| Secret for a plugin MCP (e.g. `github`) | Your shell environment, exported before launching `claude` | No |

`~/.zshrc` exports only reach Claude Code when it is started from a terminal. A session
launched from an editor or app that doesn't load your shell profile won't see them; for
those, prefer a standalone MCP with `-e`.

Check that a project's `settings.local.json` is ignored before writing to it
(`git check-ignore .claude/settings.local.json`). If a team repo tracks it, unstage it
(`git rm --cached`) and add it to `.git/info/exclude`.
