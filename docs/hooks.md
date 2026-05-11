# Hooks

Lifecycle hooks that modify Claude Code behavior at specific points during a session. Configured in `~/.claude/settings.json` (global) or `.claude/settings.json` (per-project).

---

## PostToolUse

### auto-format.sh

Auto-formats files after Edit/Write operations. Detects the project stack automatically via local binaries (`node_modules/.bin`, `vendor/bin`). Supports ESLint/Prettier (JS/TS/CSS) and PHP-CS-Fixer/Pint. Always exits 0 so formatter failures never block Claude.

Wire it globally:

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

### json-lint

Inlined PostToolUse hook that validates any edited `.json` file has valid syntax via `jq .`.

---

## PreToolUse (Safety Guards)

### docker-volume-guard

Blocks `docker compose down -v`/`--volumes` and `docker volume rm`/`remove`/`prune`. These commands destroy persistent data volumes, and the impact is irreversible. The hook exits 2 (block), showing a message asking the user to confirm manually.

### wrangler-production-guard

Blocks `wrangler d1 execute` and `wrangler d1 migrations apply` commands unless `--local` is specified. These commands could target production D1 databases.

**Key insight:** `wrangler d1 execute` **defaults to remote** when neither `--remote` nor `--local` is specified. The hook catches all three risky patterns:
- `wrangler d1 execute ...` (bare — defaults to remote)
- `wrangler d1 execute ... --remote` (explicit)
- `wrangler d1 migrations apply ...` (applies migrations to remote)

Only `wrangler d1 execute --local ...` passes through.

**Additional guard:** If `CLOUDFLARE_ENV` is set in the environment, any `wrangler` command is blocked. This env var can silently select a named environment from wrangler config without an explicit `--env` flag.

### Known limitations (grep-level hooks can't prevent)

| Bypass | How |
|---|---|
| `--env` flag | Selecting an environment via `--env` is allowed (intentional by design — the user prefers explicit flags) |
| `--config` / `-c` | Points wrangler at a different config file with arbitrary DB IDs |
| `--cwd` | Changes config auto-discovery path |
| CI pipelines | GitHub Actions run wrangler directly with API tokens, not through Claude |
| `wrangler dev --remote` | Develops against remote resources (separate workflow concern) |

These are accepted trade-offs: the guard prevents accidental production SQL during interactive Claude sessions. CI and flag-based bypasses require deliberate setup, not a mistyped command.

### Wiring example

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "cmd=$(cat | jq -r '.command // \"\"'); if echo \"$cmd\" | grep -qP 'docker\\s+(compose|stack)\\s+.*\\bdown\\b.*(-v|--volumes)\\b|docker\\s+volume\\s+(rm|remove|prune)\\b'; then echo \"BLOCKED: destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this.\"; exit 2; fi" },
          { "type": "command", "command": "cmd=$(cat | jq -r '.command // \"\"'); if [ -n \"$CLOUDFLARE_ENV\" ] && echo \"$cmd\" | grep -qP 'wrangler(\\s+|$)'; then echo \"BLOCKED: CLOUDFLARE_ENV=$CLOUDFLARE_ENV is set — wrangler may silently target that environment. Unset it and use explicit --env flags instead.\"; exit 2; fi; if echo \"$cmd\" | grep -qP 'wrangler(\\s+|$)(?=.*d1\\s+(?:execute|migrations\\s+apply))(?!.*--local)'; then echo \"BLOCKED: wrangler d1 execute/migrations apply without --local targets production. Run the command manually with --remote after reviewing.\"; exit 2; fi" }
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
