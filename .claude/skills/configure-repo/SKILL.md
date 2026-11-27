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

## 1. Gather evidence

Run these, in one response:

- `python3 -I <this skill>/scripts/repo_config.py scan --project <repo>`: MCP servers
  and skills that past sessions in the repo and its worktrees called.
- `claude mcp list` from the repo (it inherits `CLAUDE_CONFIG_DIR`): the exact server
  names, which is what `disabledMcpServers` needs. The scan prints raw prefixes such as
  `claude_ai_Google_Sheets`; match them to these names.
- The repo's current `.claude/settings.json`, `.claude/settings.local.json`, `.gitignore`,
  README, stack markers (`pyproject.toml`, `package.json`, `composer.json`) and
  `git remote -v`.

The skill list for this session is in your context; that is the set to choose from.

## 2. Propose, then stop

Show one short table per kind (connectors, skills, plugins): what to turn off and the
reason for each, citing the scan count or the repo fact. Mark anything decided without
history as a guess. Keep anything that was used, and say so. Stop and wait for the
user's OK or edits.

## 3. Apply

- Connectors: `repo_config.py disable-mcp --project <repo> "<name>" ...`. It merges with
  the existing list and backs up `.claude.json` first; report the backup path.
- Skills and plugins: merge into `.claude/settings.local.json` with `jq`, never
  overwrite keys that are already there. Use `user-invocable-only` for skills.
- Language servers: run `project-init` from claude-dotfiles if the stack's LSP isn't
  enabled yet.
- Add `.claude/settings.local.json` to `.gitignore` if it isn't covered.

## 4. Verify and report

Re-read `.claude.json` to confirm the list was written, and validate the settings file
with `jq empty`. Tell the user the changes load at the next session start, where `/mcp`
should list only what was kept, and that worktrees at other paths are not covered.
