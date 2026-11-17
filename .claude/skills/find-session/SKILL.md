---
name: find-session
description: "Trigger: which session did we..., find that conversation where, resume the session about X, in which claude session. Search past Claude Code transcripts by remembered keywords and return the session id plus its resume command. Also renders a session (or a repo's newest sessions) as readable text for reading, retros or a sub-agent."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.2"
---

## Activation Contract

Load when the user wants to find or reopen a past Claude Code session from keywords or a topic they remember. Not for recalling decisions or facts (that is Engram `mem_search`).

## Hard Rules

- Read-only. Never edit, move or delete transcripts.
- Transcripts may hold PHI or client data. Quote only the short snippets the script prints, and never send them to an external tool.

## Steps

1. Run `python3 ~/.claude/skills/find-session/scripts/find_session.py <terms...>`. Every term must match. Add `-p <project-substring>` when the user names a project and `-d <days>` when they give a time hint.
2. Use short single-concept terms, such as a ticket id, a PR number, a repo name or a distinctive word. People are often named by nickname (Felipe or Feli), so on a miss drop terms or try variants before concluding.
3. If nothing matches, retry with `--tools`, which also searches tool output (PR diffs, gh output).
4. Answer with the top session id, its last-active date, one line on why it matches (opened prompt, PRs, snippet), and the `resume:` command. Mention a runner-up only if the scores are close.
5. To read the session rather than resume it, render it (see "Render a session as readable text" below).

## Script flags

| Flag | Effect |
|---|---|
| `-p allswell` | project dir name contains the substring |
| `-d 7` | active in the last 7 days |
| `-n 10` | show 10 sessions (default 5) |
| `--tools` | also search tool output (noisier) |
| `--include-current` | do not hide the running session |
| `--config-dir ~/.claude-work` | search only that config dir. Default: `$CLAUDE_CONFIG_DIR`, else both `~/.claude` and `~/.claude-work`. The `resume:` line gets a `CLAUDE_CONFIG_DIR=` prefix for sessions outside `~/.claude` |
| `--pick` | interactive fzf picker; Enter resumes the session. Only for the user's own terminal: never run it from the Bash tool, it needs a TTY |

Ranking is TF-IDF with square-root length normalization: rare terms count more, and a short session about the topic beats a long one that mentions it in passing. The script docstring explains why BM25 was rejected.

## Render a session as readable text

Use `scripts/render_session.py` when someone, or a sub-agent, needs to read a session, not
just find it: after a compaction, to inspect a worker's session, or for a retro. Raw jsonl is
mostly tool output, and a long session can pass 100 MB. Don't write a one-off parser; this
script already handles the format.

```bash
python3 ~/.claude/skills/find-session/scripts/render_session.py --session <id-prefix | path.jsonl> --out <dir>
python3 ~/.claude/skills/find-session/scripts/render_session.py --session <id> --errors-only --out <dir>
python3 ~/.claude/skills/find-session/scripts/render_session.py --session <id> \
    --since 2026-11-07T04:00 --until 2026-11-07 --out <dir>
python3 ~/.claude/skills/find-session/scripts/render_session.py --repo <repo-path> --count 5 \
    --exclude <current-session-id> --also-prefix ~/orca/workspaces/<repo> --out <dir>
```

- The output keeps user turns, assistant text, tool calls, truncated results and tool errors.
  It drops sidechains, except when `--session` is given the path of a sub-agent file under
  `<session>/subagents/`. Compaction summaries are tagged `COMPACT SUMMARY`.
- `--errors-only` prints only tool-error lines, one per line, each naming the tool.
- `--since`/`--until` filter records by time. Times are UTC, like the printed `[timestamp]`; a
  value without a timezone is read as UTC, and a date-only `--until` covers that whole day.
  `--max-chars N` shortens every line kind.
- `--repo` also picks up the repo's worktree project dirs (`<slug>-wt-*`), where worker and
  reviewer sessions live, and guesses each session's role.
- `--also-prefix <path>` (repeatable, only with `--repo`) adds project dirs under another path.
  Orca worker sessions live under `~/orca/workspaces/<repo>/<name>`, which never starts with the
  repo's own slug, so pass that path to find them; they are labelled `worker`. A path matches a
  project dir that equals its slug or continues with `-` (slugs turn `/` into `-`, so
  `.../backend` also matches a repo named `backend-api`).
- Sessions bigger than `--chunk-bytes` (default 750000) are split into `.partN.txt` files, so a
  sub-agent can read each part whole. The jsonl is streamed, so a 120 MB session renders in
  well under a second with about 20 MB of memory.
- Transcripts are searched under `$CLAUDE_CONFIG_DIR/projects` or, when that is unset, both
  `~/.claude` and `~/.claude-work`. `--config-dir` restricts it to one.
- Write output to a scratch dir, never a repo. The text can hold secrets or client data, under
  the same rule as the Hard Rules above.
