---
name: token-report
description: Show a Claude Code usage report — model token breakdown, estimated costs, top projects, and session patterns. Delegates to the stats-analyzer subagent (Haiku) to avoid polluting the main context with raw data.
disable-model-invocation: true
---

Delegate to the `stats-analyzer` subagent to generate the usage report.

Do not run any analysis yourself. Do not explain what you're about to do. Invoke the subagent immediately and present its output as-is.

After presenting the report, offer one line: "Want me to dig into any of these areas further?"
