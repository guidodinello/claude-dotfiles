@guidelines/tools/engram.md
@guidelines/tools/RTK.md
@guidelines/tools/github-accounts.md

@guidelines/client-issue-workflow.md

@guidelines/reasoning-discipline.md
@guidelines/debugging-patterns.md

@RTK.md


<!-- lightit-ai:engram -->
## Memory
You have access to Engram persistent memory via MCP tools (mem_save, mem_search, mem_session_summary, etc.).
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
<!-- /lightit-ai:engram -->
