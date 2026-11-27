---
name: configure-repo
description: "Trims one repo's Claude Code setup to what it uses: disables unused claude.ai connectors, hides skills that don't apply, sets the stack's language servers. Decides from the repo's session history when there is one. Run only by typing /configure-repo."
disable-model-invocation: true
---

# Configure a repo

The procedure, the file each change goes to, and the reasons live in
`docs/plugins-lsp-mcp-guide.md` § "Onboarding a project" in claude-dotfiles. Read that
section first; this skill only carries it out. The target is the current working
directory unless the user names another path.

**One account at a time.** Session history, `disabledMcpServers` and connectors are per
Claude config dir (`$CLAUDE_CONFIG_DIR`, default `~/.claude`). This run configures the
account this session runs under; don't pass `--config-dir` unless the user names another
account. Usage under another account is not evidence for this one (a connector used only
from the personal account may be unusable from the work one), but you may mention it.

**Repo settings are shared by both accounts.** `.claude/settings.json` and
`.claude/settings.local.json` belong to the repo, not the account, so a skill hidden here
is hidden for every account. Read the file's existing `skillOverrides` first, and don't
hide a skill the other account may use: if you can, also run `scan --config-dir` for the
other account (`~/.claude-work` or `~/.claude`) and keep anything it shows as used.

## 1. Gather evidence

Run these, in one response:

- `python3 -I <this skill>/scripts/repo_config.py scan --project <repo>`: this account's
  sessions in the repo and its worktrees (live and deleted), the servers already
  disabled there, the MCP servers called, and the skills and slash commands used.
- `claude mcp list` from the repo. It health-checks every server, so it takes a while.
  Its names are what `disabledMcpServers` stores, prefix included: `claude.ai Google
  Sheets`, `claude.ai monday.com`. The scan prints raw tool prefixes
  (`claude_ai_Google_Sheets`); match them by eye.
- `enabledPlugins` and `skillOverrides` in `$CLAUDE_CONFIG_DIR/settings.json` and in the
  repo's `.claude/settings.json` and `.claude/settings.local.json`.
- Stack markers anywhere in the repo, not only at the root (`git ls-files` for
  `pyproject.toml`, `package.json`, `composer.json`, `svelte.config.*`), the README, and
  `git remote -v`.
- The top-level folders on disk (`ls -A`), not only what git tracks. Local work folders
  such as `my-dev-things/` are usually hidden from git by `.git/info/exclude` or a global
  ignore, so `git ls-files` and `git status` never show them. Before using "the repo has
  no X" as a reason, check the filesystem.
- `git check-ignore -q .claude/settings.local.json` (a global ignore may already cover it).

## 2. Propose, then stop

Decision rules:

- **Connectors.** Only `claude.ai …` entries are candidates; standalone and plugin
  servers (engram, easel) are out of scope. Disable every connector with zero calls,
  including unauthenticated and failing ones, unless the README or the work clearly needs
  it (a Linear-tracked repo keeps Linear). With no history, decide from the repo alone.
  Re-enabling is one toggle in `/mcp`, so disabling is the cheap side to err on.
- **Skills.** Candidates are skills in your session list that the global `skillOverrides`
  doesn't already set to `off` or `user-invocable-only`. A skill the scan shows as used
  stays on, even if it's missing from your list. Hide a skill only when its trigger can't
  match work in this repo (PR skills with no remote, Light-it brand and office-file
  skills in a personal repo, frontend skills with no frontend). When unsure, keep it.
  Under about 10 sessions, mark every skill row as a guess.
- **Plugins.** Propose only the stack's language server (`project-init`) or turning off one
  that doesn't match the stack. Committed `.claude/settings.json` for the user's own
  repos (remote owner `guidodinello`), `settings.local.json` otherwise.

Show one short table per kind with something to change, each row with its reason (the scan
count or the repo fact). For a kind with nothing to change, write one line saying so. List
what was kept because it was used. Stop and wait for the user's OK or edits.

## 3. Apply

- Connectors: `repo_config.py disable-mcp --project <repo> --all-unused [--keep "claude.ai
  Linear" ...]` disables every listed connector with no call in the scan, minus the kept
  ones; for a hand-picked set, pass the names instead. Don't build the list in the shell
  (arrays, command substitution): that trips Claude Code's permission check. It merges with
  the existing list and backs up `.claude.json` first; report the backup path.
- Skills: merge into `skillOverrides` of `.claude/settings.local.json` with `jq`, creating
  the file if needed and never overwriting keys already there. Use `user-invocable-only`.
  If you back the file up first, put the copy in your scratchpad, not next to the file:
  a `.bak` in the repo is untracked clutter that no ignore rule covers.
- Language servers: run `project-init` from claude-dotfiles (`--local` for team repos).
- If `git check-ignore` said `.claude/settings.local.json` isn't ignored, add it to `.gitignore`.

## 4. Verify and report

Re-run `scan` and check the "already disabled" list, and validate settings files with
`jq empty`. Tell the user the changes load at the next session start, where `/mcp`
should list only what was kept, that worktrees at other paths are not covered, and that
the other account (if any) was not touched.
