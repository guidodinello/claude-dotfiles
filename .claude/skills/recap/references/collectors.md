# Collector prompts

The main agent resolves every placeholder before launching, so subagents read no config:

| Placeholder | Source |
|---|---|
| `{FROM}` `{TO}` | the window, YYYY-MM-DD |
| `{START_MS}` `{END_MS}` | window bounds in epoch ms, local timezone |
| `{CLICKUP_ME}` | `clickup_resolve_assignees` with `me` |
| `{FOLDER}` | "ClickUp folder" in the workspace CLAUDE.md; omit the folder filter when absent |
| `{SLACK_ME}` | "Current logged in user's user_id" in the Slack search tool description |

Both collectors are read-only and return only the JSON described.

## ClickUp collector

```
Read-only. Collect my ClickUp activity between {START_MS} and {END_MS} (epoch ms). My user ID is {CLICKUP_ME}.

First load the tools: ToolSearch "select:mcp__claude_ai_ClickUp__clickup_filter_tasks,mcp__claude_ai_ClickUp__clickup_get_task_comments,mcp__claude_ai_ClickUp__clickup_get_bulk_tasks_time_in_status".

1. clickup_filter_tasks(assignees=["{CLICKUP_ME}"], folder_ids=["{FOLDER}"], order_by="updated", include_closed=true).
   Results come newest-updated first. Keep candidates with date_updated >= {START_MS} (later updates do not
   exclude a task). Fetch the next page only while the page's last task has date_updated >= {START_MS}.
2. clickup_get_bulk_tasks_time_in_status for the candidates: record status changes whose start time is inside the window.
3. clickup_get_task_comments per candidate: keep comments I wrote inside the window.
4. Keep only tasks with a status change or a comment of mine inside the window. Flag 3+ status changes landing
   within 5 seconds of each other as "bulk" (automation, not me).

Never quote comment text. Summarize each of my comments in at most 8 words of work content.
Return only JSON:
{"tasks":[{"id":"DEV-123","name":"...","url":"...","status_now":"...","changes":["pr pending -> ready to test (dev)"],
  "bulk":false,"my_comments":["<=8-word summary"]}],"error":null}
```

## Slack collector

```
Read-only. Collect my Slack activity from {FROM} to {TO} inclusive. My user ID is {SLACK_ME}.

First load the tool: ToolSearch "select:mcp__claude_ai_Slack__slack_search_public_and_private".

1. Search with filters "from:<@{SLACK_ME}> on:{FROM}" for one day, or "from:<@{SLACK_ME}> after:<FROM-1> before:<TO+1>"
   for a range. Use response_format="concise", include_context=false, limit=20, and follow the cursor until exhausted.
2. Group messages by channel/DM and by thread. Keep only work topics: PRs, tickets, deploys, reviews,
   decisions, questions asked or answered. Drop greetings, jokes, kudos and personal chat.
3. For each work group, extract ticket IDs ([A-Z]+-\d+) and PR numbers mentioned.

Never quote message text and never include patient names or any health data. Summarize each group
in at most 12 words.
Return only JSON:
{"groups":[{"where":"#channel or DM with <first name>","summary":"<=12 words","tickets":["DEV-123"],
  "prs":["longevity-back#407"],"open_question":false}],"error":null}
```
