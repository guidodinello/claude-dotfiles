## Memory
You have access to Engram persistent memory via MCP tools.
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
- Engram tools are deferred in Claude Code: load them with `ToolSearch("select:mcp__plugin_engram_engram__<tool>")` before the first call. The plugin's SessionStart hook says "no ToolSearch needed"; that is wrong here. A missing tool means "not loaded yet", not "Engram unavailable".
- When searching memory, use short single-concept keywords rather than combined phrases. If the first search misses, retry with shorter, broader terms before concluding nothing exists.
