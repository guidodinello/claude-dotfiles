## Engram (in addition to the Memory block)

Engram's MCP server instructions own the protocol. Local rules on top of it:

- Tools are deferred in Claude Code: load them with `ToolSearch("select:mcp__engram__<tool>")` before the first call. The SessionStart hook's "no ToolSearch needed" is wrong here. A missing tool means "not loaded yet", not "Engram unavailable".
- Save verified, durable conclusions (decisions, bugfixes, discoveries, conventions, config changes), grouped by topic, without waiting to be asked. Not every event. Use `capture_prompt: false` for automated/SDD artifacts.
- Past work: `mem_context` → `mem_search` → `mem_get_observation`. Search with short single-concept keywords; if the first search misses, retry broader before concluding nothing exists.
- Call `mem_session_summary` on explicit closure or handoff, not on every "done".
- `mem_judge_many` takes a `judgments` array.
- Memory work is bookkeeping, never the reply. Finish it before the final answer, which has no tool calls after it. A failed or timed-out memory call never blocks or replaces the answer.
