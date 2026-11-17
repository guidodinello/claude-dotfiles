# Hooks

Lifecycle hooks that modify Claude Code behavior at specific points during a session. Configured in `~/.claude/settings.json` (global) or `.claude/settings.json` (per-project).

---

## PostToolUse

### auto-format.sh (opt-in, per project)

Auto-formats files after Edit/Write operations. Detects the project stack automatically via local binaries (`node_modules/.bin`, `vendor/bin`). Supports ESLint/Prettier (JS/TS/CSS) and PHP-CS-Fixer/Pint. Always exits 0 so formatter failures never block Claude.

`sync.sh` puts the script in every config dir but **does not wire it**, on purpose: run globally, it would apply each project's `eslint --fix` or formatter to every file Claude edits, changing lines outside the edit and widening diffs in repos that don't expect it. A project that wants it opts in from its own `.claude/settings.json` (or `settings.local.json` in a team repo):

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

A project that needs different formatting rules creates its own `.claude/hooks/auto-format.sh`; the shared script hands over to it.

### json-lint.sh

Wired globally from `settings.base.json`. After an Edit/Write to a `.json` file, checks that it still parses (`jq empty`) and, if not, exits 2 so the error reaches Claude. The edit has already happened; nothing is blocked. Skips JSON-with-comments files (`tsconfig*.json`, `jsconfig*.json`, `devcontainer.json`, anything under `.vscode/`).

---

## PreToolUse (Safety Guards)

The two Bash guards live in one script, `.claude/hooks/guard-bash.sh`, registered on the `Bash` matcher. It reads the command from `.tool_input.command` and matches with bash's own `[[ =~ ]]`, so it needs no GNU grep. It fails closed: if the hook input can't be read (no `jq`, or an unexpected shape), the command is blocked.

### docker-volume-guard

Blocks `docker compose down -v`/`--volumes` and `docker volume rm`/`remove`/`prune`. These commands destroy persistent data volumes, and the impact is irreversible. The hook exits 2 (block), showing a message asking the user to confirm manually.

### wrangler-production-guard

Blocks `wrangler d1 execute` and `wrangler d1 migrations apply` commands unless `--local` is specified. These commands could target production D1 databases.

**Key insight:** `wrangler d1 execute` **defaults to remote** when neither `--remote` nor `--local` is specified. The hook catches all three risky patterns:
- `wrangler d1 execute ...` (bare — defaults to remote)
- `wrangler d1 execute ... --remote` (explicit)
- `wrangler d1 migrations apply ...` (applies migrations to remote)

Only `wrangler d1 execute --local ...` passes through. Each simple command (split on `;`, `&`, `|`, parentheses, backticks and newlines, outside quotes) is judged on its own, and three cases are blocked rather than guessed at:

- `--local` that is not a standalone flag, or that only appears inside a quoted string. Put `--local` before any quoted argument.
- `--remote`, `--no-local`, `--local=...` or `--local` followed by anything other than another option or a redirect (`--local false`, `--local $X`, `--local db`) anywhere in the same command, quoted or not, even next to `--local`.
- A `wrangler d1` write that only appears inside quoted text, such as `sh -c "wrangler d1 execute ..."`.
- A command longer than 4000 characters that contains a `wrangler d1` write. Use `--file` for long SQL.

A versioned package name (`npx wrangler@3 ...`) and a quoted or backslash-escaped `wrangler` are matched too.

**Additional guard:** If `CLOUDFLARE_ENV` is set in the environment, any `wrangler` command is blocked. This env var can silently select a named environment from wrangler config without an explicit `--env` flag.

### env-file-guard

`.claude/hooks/guard-env-files.sh`, registered on `Read|Edit|Write|NotebookEdit|Grep`. Blocks (exit 2) any file whose basename is an env file, **anywhere on disk**: it starts with `.env` (`.env`, `.env.local`, `.env.backup`, `.envrc`) or ends in `.env` (`prod.env`). The example files stay allowed: `.env.example`, `.env.*.example`, `.env.sample`, `.env.template`. Names are compared lowercased (macOS volumes are case-insensitive), and each hop of a symlink chain is checked (relative targets against the link's directory, a leading `~/` against `$HOME`), so a link named `notes` that points at `.env` is blocked. A loop or a chain over 40 hops is blocked. Every path field in the call (`file_path` and `notebook_path`) is judged. `.envrc` is blocked because the in-project `Read(.env*)` deny already blocks it.

Why a hook next to the deny rules in `settings.base.json`: a bare `Read(.env*)` rule only reaches the current directory, and a `!` carve-out cannot reach a `//` or `~/` anchored rule (the docs read a `!` pattern relative to the current directory). So the base denies the real-file names anchored at `//**/`, which keeps `.env.example` readable, and this hook closes the rest (`.env.backup`, `.env.prod`) by name. The deny rules stay as defense in depth when hooks are off.

It fails closed like `guard-bash.sh`: if `jq` is missing, the input can't be parsed, or there is no usable path, the call is blocked.

**Grep:** Claude Code 2.1.327 exposes no `Grep` or `Glob` tool (searches run through `Bash`), so this branch only matters for versions or SDK sessions that still have the tool; it is covered by unit tests, not a live run. Only a `path` that is itself an env file is blocked. A directory path, or no path, is allowed: the guard can't see inside the search, so a directory search can still read unlisted env files there; Claude Code applies `Read` deny rules to the searched directory on a best-effort basis. A `glob` filter aimed at env files (`.env*`, `*.env`) is blocked. `Glob` (names only) is not covered, and Bash `cat` and redirects stay on the deny rules above.

### Known limitations (pattern-level hooks can't prevent)

| Bypass | How |
|---|---|
| Shell expansion | `$W d1 execute`, `wrangler d1 $SUB`, `eval`, a script file: the text the guard sees is not the command that runs |
| `--env` flag | Selecting an environment via `--env` is allowed (intentional by design — the user prefers explicit flags) |
| `--config` / `-c` | Points wrangler at a different config file with arbitrary DB IDs |
| `--cwd` | Changes config auto-discovery path |
| CI pipelines | GitHub Actions run wrangler directly with API tokens, not through Claude |
| `wrangler dev --remote` | Develops against remote resources (separate workflow concern) |

These are accepted trade-offs: the guard prevents accidental production SQL during interactive Claude sessions. CI and flag-based bypasses require deliberate setup, not a mistyped command.

### Wiring example

`sync.sh` writes this from `settings.base.json`, resolving the path per config dir:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/guard-bash.sh" }
        ]
      },
      {
        "matcher": "Read|Edit|Write|NotebookEdit|Grep",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/guard-env-files.sh" }
        ]
      }
    ]
  }
}
```

---

## Status Line

### statusline.sh

Status bar rendered by Claude Code's `statusLine` feature. Displays model name, directory, git branch + staged/modified counts, context window usage bar with cost, and 5h/7d rate-limit percentages with reset times.

Wire it globally:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "refreshInterval": 30
  }
}
```
