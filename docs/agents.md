# Agents

Subagents invoked by Claude during tasks. These are defined in `.claude/agents/` and referenced by skills or project CLAUDE.md files.

| Agent | Description |
|---|---|
| `audit-finding-verifier` | Verifies a single audit finding against the codebase; confirms, false-positive, or partially accurate |
| `quality-checker` | Runs the full QA pipeline and returns a concise summary of issues |
| `slite-sync` | Syncs a local Markdown file to a Slite document |
| `stats-analyzer` | Analyzes `stats-cache.json` and `history.jsonl` for token/cost usage reports |
