---
name: recap
description: "Trigger: recap, what did I do on <day>, yesterday's activity, standup/daily prep. Rebuild my GitHub, git, ClickUp and Slack activity for a day or range, grouped by ticket."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when the user asks what they did on a day or range, wants a recap of yesterday, or prepares a standup/daily. Not for planning today (that is the `morning` skill).

## Hard Rules

- Read-only. Never post, comment, update a status, or create anything in any source.
- Day boundaries are the machine's local timezone (`date +%z`), never UTC.
- Never quote Slack or ClickUp message text. Summarize work content in a few words; drop social chatter. If content may contain PHI, keep only the ticket ID and a neutral label.
- A failed source is reported as failed in the output; the rest continue.
- Every bullet links to its source (PR URL, ClickUp task link, Slack permalink when available).

## Decision Gates

| Input | Window |
|---|---|
| none | previous working day (Monday → last Friday) |
| `yesterday`, `today`, `YYYY-MM-DD` | that day |
| `FROM..TO` | inclusive range |

## Execution Steps

1. Resolve the window to `FROM` and `TO` (YYYY-MM-DD) and the placeholders listed in [references/collectors.md](references/collectors.md): IDs, epoch bounds, and the ClickUp folder from the workspace CLAUDE.md "ClickUp folder" line (none if absent).
2. In parallel:
   - Run `bash ~/.claude/skills/recap/scripts/code-activity.sh FROM TO "$PWD"`: PRs opened/merged and reviews submitted in the window, plus local commits on all branches.
   - Launch the ClickUp and Slack collectors as two background `general-purpose` subagents (`model: sonnet`) with the filled prompts from the references. They return compact JSON only.
   - `mem_search` engram for each day's date strings (`2026-10-01`, `1 Oct 2026`) and keep session summaries/decisions from the window; use them for the *why* behind items.
3. Extract ticket IDs (`[A-Z]+-\d+`) from PR titles, commit subjects, Slack summaries and ClickUp tasks (never from branch names: commits reach many branches). Group every item under its ticket; items with none go under **Other**.
4. Fetch name and current status for any ticket ID seen in GitHub/Slack but missing from the ClickUp result (`clickup_get_task`).
5. Collapse noise: a squash commit that duplicates a merged PR, sync/backmerge PRs into one line, bulk ClickUp updates sharing the same second (automation, not you).
6. Derive **Next** from what is still open: open PRs, tasks `in progress`/`pr pending`, unanswered threads.

## Output Contract

Reply in the conversation language, in chat:

```
<Weekday D Mon> (or the range)
- DEV-123 <task name, short>: <what happened: PR opened/merged/reviewed, status change, decision>
- Other: <items without a ticket>
Next: <open PRs and in-progress tasks>
Blockers: <PRs waiting on others, open questions>
Sources: GitHub ✓ · git ✓ · ClickUp ✓ · Slack ✓ · engram ✓ (✗ + reason when one failed)
```

Max ~10 ticket bullets; merge minor ones. No raw event dumps.

## References

- [references/collectors.md](references/collectors.md) — ClickUp and Slack subagent prompts.
- [scripts/code-activity.sh](scripts/code-activity.sh) — GitHub + git collector; prints one JSON object.
