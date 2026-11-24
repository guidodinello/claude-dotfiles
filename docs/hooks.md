# Hooks

Lifecycle hooks that modify Claude Code behavior at specific points during a session. Configured in `~/.claude/settings.json` (global) or `.claude/settings.json` (per-project).

---

## PostToolUse

### auto-format.sh (opt-in, per project)

Auto-formats files after Edit/Write operations, by extension. It never installs or calls a project script alias; JS/TS, CSS/Markdown, JSON/YAML and PHP run only a binary the project itself ships, and Python runs a formatter found on the machine's `PATH`:

| Files | Tool | Where it comes from |
|---|---|---|
| `ts` `tsx` `js` `jsx` | `eslint --fix` | `node_modules/.bin` of the project |
| `css` `scss` `md`, `json` `yaml` `yml` | `prettier --write` | `node_modules/.bin` of the project |
| `php` | Pint, else PHP-CS-Fixer | `vendor/bin` of the project |
| `py` `pyi` | `ruff format` and `ruff check --fix`, else `black` | global, found with `command -v` |

Always exits 0 so formatter failures never block Claude.

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

## Stop

### dev-docs-index-check.py

Wired globally from `settings.base.json` on `Stop`. When the session's cwd has a `my-dev-things/` folder and a doc or script in it (`.md`, `.sh`, `.py`, `.mjs`, `.html`) changed since the session started, it runs the `dev-docs-index` skill's `check_index.py`. The session start is the first timestamped transcript entry, because Linux has no file creation time and the transcript's ctime moves with every message. Logs a running stack keeps rewriting don't count.

It keeps findings about folders that changed: a gap in a folder where a doc or script changed, or a missing README or unnamed subfolder on the path down to one. Those last two count even when they are old, because without them the new work is unreachable. An old unnamed file in a parent, or any gap in an unrelated folder, does not block. On findings it exits 2, so Claude keeps going and fixes them before it stops.

- **Why Stop, not PostToolUse:** most edits there go through Bash, and an index is legitimately incomplete mid-task.
- **Failing safe:** it fails open (bad input, an unreadable transcript or a missing checker exits 0) and exits 0 when `stop_hook_active` is set, so it blocks at most once per turn and does not re-check the fix.
- **Not covered:**
  - attribution: "changed" is mtime against the session start, so a doc another session or a manual edit wrote anywhere under `my-dev-things/` counts as this session's, and its gaps are reported here;
  - a deleted or moved file;
  - worktree sessions, whose cwd has the `.my-dev-things` link instead of the folder.

---

## SessionStart and UserPromptSubmit

### reminders.py

Wired globally from `settings.base.json` on both events. It brings back reminders that the `/remind` skill registered (one JSON file each in `<config dir>/reminders/`, local to the machine). It doesn't use a daemon: it checks `now >= due` whenever a session starts or a prompt is sent, so a date that passed while the laptop was off fires at the next session or prompt.

- **SessionStart:** prints `session_id: <id> (remind command: ...)`, which `/remind` uses to register a reminder. It then gives the owning session the "read the plan and do it" message for each of its due reminders, once. Every other session gets a one-line digest with the resume command and no plan content. If the owner transcript was deleted, the digest line says "owner session gone: start fresh in <cwd>" instead. Reminders not yet due appear only as `N scheduled, next: <date>`.
- **UserPromptSubmit:** gives only that once-only message, to an owner session that was already open when the reminder came due. Otherwise it prints nothing.
- **Failing safe:** it always exits 0, but it never fails silently. A missing plan file and an unreadable reminder file are named in the output, and an unexpected error at SessionStart prints `reminders hook error: <type>`.

Design and decisions: [reminders.md](reminders.md).

---

## PreToolUse (Safety Guards)

Two scripts, both registered in `settings.base.json` and both policy controls that fail closed:

- `.claude/hooks/guard-bash.sh`, on the `Bash` matcher: the Docker and wrangler checks below. It reads the command from `.tool_input.command` and matches with bash's own `[[ =~ ]]`, so it needs no GNU grep.
- `.claude/hooks/guard-env-files.sh`, on `Read|Edit|Write|NotebookEdit|Grep`: see env-file-guard.

### Fail closed

Claude Code docs, on a hook that fails: "On most events, when a hook fails or times out, Claude Code still carries out the action. A policy hook with a wrong path or a crashing script then lets everything through. To block the action instead, set `"onFailure": "block"` on a `command`, `http`, or `mcp_tool` hook." A failure is a script that can't start (missing file), an exit code other than 0 or 2, or a timeout. With `"block"`, "a `PreToolUse` failure blocks the tool call".

So both guard entries carry `"onFailure": "block"` and `"timeout": 10` (seconds; the default for a command hook is 600). A guard run takes about 10 ms for a typical command and at most about 130 ms for one just under the 4000-character limit that mentions docker or wrangler (bash 3.2, measured), so 10 s is a hang, not a slow machine. `~/.claude/hooks/guard-bash.sh` is a symlink into the checkout, so checking out a branch that lacks the script, or a corrupted file, now stops the Bash tool instead of removing the brake.

**Requires Claude Code 2.1.324 or later** on every machine that syncs: `onFailure` needs v2.1.295 and the marketplace pin below needs v2.1.324. The docs say nothing on how an older version treats the unknown `onFailure` field. Check `claude --version` before syncing.

The scripts also fail closed on their own: unreadable input (no `jq`, an unexpected shape, a non-string field) exits 2.

### docker-volume-guard

Blocks the Docker commands that remove data volumes. These destroy persistent data, and the impact is irreversible. The hook exits 2 (block), showing a message asking the user to confirm manually.

- `docker compose`, `docker-compose` or `docker stack` with `down` and a volume flag.
- `docker compose` / `docker-compose` `rm` with a volume flag.
- `docker rm`, `docker container rm` and `docker container remove` with a volume flag.
- `docker system prune --volumes`.
- `docker volume rm`, `remove` and `prune`.

A volume flag is `-v`, `--volumes`, or a short flag cluster containing `v` (`-tv`, `-sfv`). Subcommands and flags are matched as whole words, so `docker compose -f down.yml up -v` and `docker compose up -d --verbose` pass. Each simple command (split on `;`, `&`, `|`, parentheses, backticks and newlines, outside quotes) is judged on its own, so a `-v` that belongs to a neighbour does not count: `docker rm c1 && docker run -d -v data:/data nginx` and `docker compose down && ls -lav` pass. Not blocked: `docker compose down` with no volume flag, `docker rm c1`, `docker compose rm -s`, `docker system prune`.

A command longer than 4000 characters is not split (the walk is quadratic in bash 3.2): it is judged as one piece, as it was before the split, so a volume flag anywhere in it counts.

### wrangler-production-guard

Blocks `wrangler d1 execute` and `wrangler d1 migrations apply` commands unless `--local` is specified. These commands could target production D1 databases.

**Key insight:** `wrangler d1 execute` **defaults to remote** when neither `--remote` nor `--local` is specified. The hook catches all three risky patterns:
- `wrangler d1 execute ...` (bare — defaults to remote)
- `wrangler d1 execute ... --remote` (explicit)
- `wrangler d1 migrations apply ...` (applies migrations to remote)

Only `wrangler d1 execute --local ...` passes through. Each simple command (split on `;`, `&`, `|`, parentheses, backticks and newlines, outside quotes) is judged on its own, and these cases are blocked rather than guessed at:

- `--local` that is not a standalone flag, or that only appears inside a quoted string. Put `--local` before any quoted argument.
- `--remote`, `--no-local`, `--local=...` or `--local` followed by anything other than another option or a redirect (`--local false`, `--local $X`, `--local db`) anywhere in the same command, quoted or not, even next to `--local`.
- A `wrangler d1` write that only appears inside quoted text, such as `sh -c "wrangler d1 execute ..."`.
- A command longer than 4000 characters that contains a `wrangler d1` write. Use `--file` for long SQL.

A versioned package name (`npx wrangler@3 ...`) and a quoted or backslash-escaped `wrangler` are matched too.

**Additional guard:** If `CLOUDFLARE_ENV` is set in the environment, any `wrangler` command is blocked. This env var can silently select a named environment from wrangler config without an explicit `--env` flag.

**Deletes and restores.** `delete` as a wrangler subcommand word is blocked (`d1 delete`, `r2 bucket delete`, `kv namespace delete`, `secret delete`, `delete`), and so is `wrangler d1 time-travel restore`, which overwrites a database with an earlier state. Read-only commands such as `d1 list` and `d1 time-travel info` pass. "Subcommand word" means one of the first four words after `wrangler` in the same simple command; the scan ends at the first option other than `--config`, `-c`, `--cwd`, `--env` and `-e` (which are skipped with their value). So `wrangler tail --search delete`, `wrangler deploy && npm run delete` and the SQL in `d1 execute --local --command "delete from t"` pass, and `wrangler --config x d1 delete db` does not. A longer command is judged as one piece: any `delete` word after `wrangler` blocks.

### Env files in Bash

`guard-bash.sh` does not judge env or secret file names. A name check on every word of a Bash command blocks commands that only mention an env file (a commit message, a PR body, `op run --env-file=refs.env -- ./script.sh`, which `guidelines/tools/1password.md` recommends), and it costs milliseconds per word in bash 3.2, so a long heredoc would hit the hook timeout. The owner dropped it. What covers Bash is the `Read`/`Edit` deny rules in `settings.base.json` and the auto-mode classifier, and only for what they recognise: see Known limitations.

### env-file-guard

`.claude/hooks/guard-env-files.sh`, registered on `Read|Edit|Write|NotebookEdit|Grep`. Blocks (exit 2) any file whose basename is an env file, **anywhere on disk**: it starts with `.env` (`.env`, `.env.local`, `.env.backup`, `.envrc`) or ends in `.env` (`prod.env`). The example files stay allowed: `.env.example`, `.env.*.example`, `.env.sample`, `.env.template`. Names are compared lowercased (macOS volumes are case-insensitive), and each hop of a symlink chain is checked (relative targets against the link's directory, a leading `~/` against `$HOME`), so a link named `notes` that points at `.env` is blocked. A loop or a chain over 40 hops is blocked. The physical parent directory is judged too (`cd -P`), so `/tmp/x/credentials` is blocked when `/tmp/x` links to `~/.aws`. Every path field in the call (`file_path` and `notebook_path`) is judged. `.envrc` is blocked because the in-project `Read(.env*)` deny already blocks it.

Why a hook next to the deny rules in `settings.base.json`: a bare `Read(.env*)` rule only reaches the current directory, and a `!` carve-out cannot reach a `//` or `~/` anchored rule (the docs read a `!` pattern relative to the current directory). So the base denies the real-file names anchored at `//**/`, which keeps `.env.example` readable, and this hook closes the rest (`.env.backup`, `.env.prod`) by name. The deny rules stay as defense in depth when hooks are off.

It fails closed like `guard-bash.sh`: if `jq` is missing, the input can't be parsed, or there is no usable path, the call is blocked.

**Grep:** Claude Code 2.1.327 exposes no `Grep` or `Glob` tool (searches run through `Bash`), so this branch only matters for versions or SDK sessions that still have the tool; it is covered by unit tests, not a live run. Only a `path` that is itself an env file is blocked. A directory path, or no path, is allowed: the guard can't see inside the search, so a directory search can still read unlisted env files there; Claude Code applies `Read` deny rules to the searched directory on a best-effort basis. A `glob` filter spelled as an env name (`.env*`, `*.env`) is blocked, on a best-effort basis: the text is not expanded, so `.e*` or `{.env,x}` get through, as does a search with no glob at all. `Glob` (names only) is not covered.

**Secret files other than env files.** The guard blocks these too, and `settings.base.json` carries a matching `Read`/`Edit` deny rule for each shape (the `~/` rules are anchored at the home directory, the `//` rules at the filesystem root; a bare pattern such as `Read(.ssh/*)` is relative to the current directory, which is why an installer's un-anchored rule protects nothing outside a project). `is_secret_path` in the script is the definition, and `tests/test_guard_env_files.py` checks the deny rules against it in both directions:

- a `.dev.vars` or `.dev.vars.*` basename (so `.dev.vars.example` is blocked as well: a `!` carve-out cannot reach an anchored `//` rule, so the hook does not allow what the rule denies);
- anything under a `.aws` directory;
- a private SSH key under a `.ssh` directory: `*_rsa`, `*_dsa`, `*_ecdsa`, `*_ed25519`, `*_ecdsa_sk`, `*_ed25519_sk` or `*.pem` (the `.pub` files, `config` and `known_hosts` stay readable);
- the `.npmrc` in the home directory (`~/.npmrc`; a project `.npmrc` stays readable).

Bash is not covered by this script (see Env files in Bash). Claude Code docs, on the deny rules: "Read and Edit deny rules apply to Claude's built-in file tools. In a Bash command Claude Code can analyze, they also apply to redirection targets and to file commands it recognizes, such as `cat`, `head`, `tail`, `sed`, and `tee`." Per the same page they do not apply to `grep -r` or to scripts.

### Known limitations (pattern-level hooks can't prevent)

All the guards read text; none runs the command. Each of these gets past them:

| Bypass | How |
|---|---|
| Shell expansion | `$W d1 execute`, `wrangler d1 $SUB`, `eval`, a script file: the text the guard sees is not the command that runs |
| An env or secret file read through Bash | By owner decision `guard-bash.sh` does not look at file names. The deny rules cover the file commands Claude Code recognises (`cat`, `head`, `tail`, `sed`, `tee`) and redirection targets, for the names they list. Not covered: a real env file under a name no rule lists read with `cat` outside the project (`.env.backup`), `source .env`, an interpreter (`python3 -c "open('.env')"`), `docker compose --env-file`, a script that opens the file itself, `grep -r` over a directory |
| A symlinked directory in a Bash command | The file-tool guard resolves the parent directory (`/tmp/x/credentials` is blocked when `/tmp/x` links to `~/.aws`); Bash is not judged at all |
| Globs and run-time names in the Grep tool's `glob` filter | `.e*` and `{.env,x}` get past the best-effort check on a `glob` that spells an env name |
| SSH keys with custom names | A private key whose name is not one of the shapes listed under env-file-guard, in the deny rules and in the hook |
| A deeper `delete` | `wrangler d1 --some-option delete db`, or `delete` as the fifth word after `wrangler`: the subcommand scan stops at the first option and at four words |
| `--env` flag | Selecting an environment via `--env` is allowed (intentional by design — the user prefers explicit flags) |
| `--config` / `-c` | Points wrangler at a different config file with arbitrary DB IDs |
| `--cwd` | Changes config auto-discovery path |
| CI pipelines | GitHub Actions run wrangler directly with API tokens, not through Claude |
| `wrangler dev --remote` | Develops against remote resources (separate workflow concern) |

These are accepted trade-offs: the guards prevent an accident during an interactive Claude session. CI and flag-based bypasses require deliberate setup, not a mistyped command.

### Out of scope by design

Recursive deletes, forced pushes, infrastructure teardown and database drops are not matched by any guard here. Sessions run in auto mode, where the auto-mode classifier judges each action that no allow or deny rule decides; "Actions matching your allow, ask, or deny rules resolve immediately" (permission-modes docs), so keep the allow list narrow, as the base does for `rtk` (only `rtk gain`). What the guards add are the few cases the classifier should never be left to guess: Docker volume loss, wrangler production targets, and wrangler deletes and restores. Reading an env or secret file through Bash under a name the deny rules do not list, or through an interpreter, is also left to the classifier, by owner decision.

A hook that exits 2 wins over an allow rule: "A hook that exits with code 2 stops the tool call before permission rules are evaluated, so the block applies even when an allow rule would otherwise let the call proceed." (permissions docs)

### Engram marketplace pin

`extraKnownMarketplaces.engram.source.ref` in `settings.base.json` is a full commit SHA. Claude Code docs: "To keep refreshes and auto-updates from moving a `github` or `git` marketplace off a commit you've reviewed, set `ref` to that commit's full SHA". **Requires Claude Code 2.1.324 or later**: "versions before v2.1.324 can't load a marketplace pinned this way".

To bump the pin:

1. Resolve the new commit: `gh api repos/Gentleman-Programming/engram/commits/main --jq .sha`.
2. Review the diff since the pinned commit (`gh api repos/Gentleman-Programming/engram/compare/<pinned>...<new>`, or the compare page on GitHub).
3. Edit `ref` in `settings.base.json` and run `./sync.sh`.

### Wiring example

`sync.sh` writes this from `settings.base.json`, resolving the path per config dir:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/guard-bash.sh", "onFailure": "block", "timeout": 10 }
        ]
      },
      {
        "matcher": "Read|Edit|Write|NotebookEdit|Grep",
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/guard-env-files.sh", "onFailure": "block", "timeout": 10 }
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
