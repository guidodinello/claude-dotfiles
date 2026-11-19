## Memory
You have access to Engram persistent memory via MCP tools.
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
- Engram tools are deferred in Claude Code: load them with `ToolSearch("select:mcp__engram__<tool>")` before the first call. The plugin's SessionStart hook says "no ToolSearch needed"; that is wrong here. A missing tool means "not loaded yet", not "Engram unavailable".
- `mem_judge_many` takes a `judgments` array.
- A save that fails with "multiple active runtime sessions match" is not lost: retry once with `session_id` set to the current Claude Code session ID (the UUID in the scratchpad or transcript path). Engram registers the Claude Code session IDs, so this resolves it. `engram doctor` lists the candidates; end only sessions confirmed dead with `mem_session_end`.
- When searching memory, use short single-concept keywords rather than combined phrases. If the first search misses, retry with shorter, broader terms before concluding nothing exists.
