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
| `/address-pr-comments` | Fetches unresolved PR review threads, fixes valid ones, commits and pushes, then replies |
| `/audit-consolidation-validator` | Validates and repairs a client-facing consolidated audit document against internal audit files |
| `/audit-fact-checker` | Verifies reported audit findings against the actual codebase to confirm real bugs vs. false positives |
| `/clean-permissions` | Generalizes overly-specific Bash permission rules in settings files |
| `/clickup-create-ticket` | Creates Bug/Improvement/Task tickets in ClickUp for the active project |
| `/clickup-task-description` | Writes a QA-oriented ClickUp subtask description for completed backend work |
| `/code-health` | Codebase readiness audit: type safety, dead code, test coverage, complexity, deps |
| `/conventional-commits` | Generates granular conventional commits from staged changes |
| `/db-migration-planner` | Plans a database migration between providers with schema and data steps |
| `/db-scalability-audit` | Database scalability & architecture audit with provider-specific limits |
| `/figma-to-tailwind` | Implements UI components from Figma designs using Tailwind 4 + tailwind-variants |
| `/git-brag` | Finds your commits on a path, formatted for perf-review docs |
| `/hipaa-audit` | HIPAA Security Rule compliance audit for healthcare codebases |
| `/improve-codebase-architecture` | Surfaces architectural friction and proposes deepening opportunities — refactors that turn shallow modules into deep, testable, AI-navigable ones † |
| `/markdown-to-slite` | Syncs a local Markdown file to a Slite document (local file is source of truth) |
| `/meta-skill-db-scalability-audit-improver` | Refreshes provider limits and anti-patterns in the db-scalability-audit skill |
| `/meta-skill-hipaa-audit-improver` | Refreshes regulatory guidance and enforcement cases in the hipaa-audit skill |
| `/meta-skill-security-audit-improver` | Refreshes OWASP, CWE Top 25, and NIST guidelines in the security-audit skill |
| `/permissions-audit` | Comprehensive authorization audit across roles, permissions, and auth logic |
| `/qa-check` | Runs type-check, linting, and tests via the quality-checker subagent (stack-agnostic) |
| `/security-audit` | Application security audit covering OWASP Top 10 vulnerability patterns |
| `/slite-compare-docs` | Compares two Slite documents to check whether one fully supersedes the other |
| `/slite-to-clickup` | Syncs a Slite document to a ClickUp Doc page (Slite is source of truth) |
| `/ticket-refinement` | Writes and refines subtasks for software tickets (endpoints, components, APIs) |
| `/token-report` | Token usage report from Claude Code stats |
| `/writing-react-effects` | Reviews/writes React components to eliminate unnecessary useEffect usage |

## Agents

| Agent | Description |
|---|---|
| `audit-finding-verifier` | Verifies a single audit finding against the codebase; confirms, false-positive, or partially accurate |
| `clickup-create-task` | Creates a single ClickUp task via REST API; receives a params file, optionally cross-comments |
| `clickup-sync` | Pushes a local Markdown file to a ClickUp Doc page via REST API |
| `quality-checker` | Runs the full QA pipeline and returns a concise summary of issues |
| `slite-sync` | Syncs a local Markdown file to a Slite document |
| `stats-analyzer` | Analyzes `stats-cache.json` and `history.jsonl` for token/cost usage reports |

## Guidelines

| File | Use |
|---|---|
| `guidelines/python.md` | Python coding guidelines — exception handling, async, generators |

Import into any project's `CLAUDE.md` with `@~/.claude/guidelines/python.md`. The file is loaded fresh each session, so it stays in sync with this repo without copying.

Add new guidelines here as you encounter patterns worth sharing across projects (e.g. `guidelines/laravel.md`, `guidelines/react.md`).

## Hooks

### PostToolUse

**`auto-format.sh`** — PostToolUse hook that auto-formats files after edits. Detects the project stack automatically via local binaries (`node_modules/.bin`, `vendor/bin`). Supports ESLint/Prettier (JS/TS/CSS) and PHP-CS-Fixer/Pint. Always exits 0 so formatter failures never block Claude.

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

**`json-lint`** — PostToolUse hook (inlined) that validates any edited `.json` file has valid syntax via `jq .`.

### PreToolUse (Safety Guards)

**`docker-volume-guard`** — Blocks `docker compose down -v`/`--volumes` and `docker volume rm`/`remove`/`prune`. These commands destroy persistent data volumes, and the impact is irreversible. The hook exits 2 (block), showing a message asking the user to confirm manually.

**`wrangler-production-guard`** — Blocks `wrangler d1 execute` and `wrangler d1 migrations apply` commands unless `--local` is specified. Blocks commands that could target production D1 databases.

**Key insight:** `wrangler d1 execute` **defaults to remote** when neither `--remote` nor `--local` is specified. The hook catches all three risky patterns:
- `wrangler d1 execute ...` (bare — defaults to remote)
- `wrangler d1 execute ... --remote` (explicit)
- `wrangler d1 migrations apply ...` (applies migrations to remote)

Only `wrangler d1 execute --local ...` passes through.

**Additional guard:** If `CLOUDFLARE_ENV` is set in the environment, any `wrangler` command is blocked. This env var can silently select a named environment from wrangler config without an explicit `--env` flag, and the user finds explicit flags more intentional.

**Known limitations (grep-level hooks can't prevent):**
| Bypass | How |
|---|---|
| `--env` flag | Selecting an environment via `--env` is allowed (intentional by design — the user prefers explicit flags) |
| `--config` / `-c` | Points wrangler at a different config file with arbitrary DB IDs |
| `--cwd` | Changes config auto-discovery path |
| CI pipelines | GitHub Actions run wrangler directly with API tokens, not through Claude |
| `wrangler dev --remote` | Develops against remote resources (separate workflow concern) |

These are accepted trade-offs: the guard prevents accidental production SQL during interactive Claude sessions. CI and flag-based bypasses require deliberate setup, not a mistyped command.

Wire safety guards globally in `~/.claude/settings.json`:

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

### Status Line

**`statusline.sh`** — status bar rendered by Claude Code's `statusLine` feature. Displays model name, directory, git branch + staged/modified counts, context window usage bar with cost, and 5h/7d rate-limit percentages with reset times. Wire it in `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "refreshInterval": 30
  }
}
```

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
