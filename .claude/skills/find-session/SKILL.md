---
name: find-session
description: "Trigger: which session did we..., find that conversation where, resume the session about X, in which claude session. Search past Claude Code transcripts by remembered keywords and return the session id plus its resume command."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
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

## Script flags

| Flag | Effect |
|---|---|
| `-p allswell` | project dir name contains the substring |
| `-d 7` | active in the last 7 days |
| `-n 10` | show 10 sessions (default 5) |
| `--tools` | also search tool output (noisier) |
| `--include-current` | do not hide the running session |
| `--pick` | interactive fzf picker; Enter resumes the session. Only for the user's own terminal: never run it from the Bash tool, it needs a TTY |

Ranking is TF-IDF with square-root length normalization: rare terms count more, and a short session about the topic beats a long one that mentions it in passing. The script docstring explains why BM25 was rejected.
