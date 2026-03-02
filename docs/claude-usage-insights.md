# Claude Code Usage Insights

Reference document for understanding token usage patterns, cost drivers, and optimization strategies.
Run `/token-report` for a live report.

---

## How to Explore Usage Data

Two data sources live in `~/.claude/`:

| File | What's in it | Freshness |
|---|---|---|
| `stats-cache.json` | Token counts per model, daily activity, session stats | Stale (updated periodically by Claude Code) |
| `history.jsonl` | Every user message with timestamp, project, sessionId | Real-time |

### Useful analysis queries

**Token breakdown per model** — `stats-cache.json → modelUsage`
- `inputTokens`: uncached direct input
- `cacheReadInputTokens`: tokens served from prompt cache (cheap)
- `cacheCreationInputTokens`: tokens written to prompt cache
- `outputTokens`: generated tokens (most expensive per-token)

**Cache hit rate** = `cacheReadTokens / (inputTokens + cacheReadTokens + cacheCreationTokens)`

**Output/Input ratio** = `outputTokens / inputTokens`
- High ratio (>1): model is doing heavy generation work
- Low ratio (<0.1): model is mostly reading context, barely generating — red flag for over-powered model

**Project activity** — `history.jsonl` grouped by `project` field

**Session patterns** — group by `sessionId`, count messages, compute duration from min/max timestamps

---

## Key Findings (Feb 2026 baseline)

### Model usage split

| Model | Sessions | Input tokens | Cache reads | Output tokens | Output/Input | Est. cost |
|---|---|---|---|---|---|---|
| sonnet-4-5 | Jan 7 only | 5,195 | 3.3M | 7,527 | **1.45x** | $2.58 |
| opus-4-5 | Jan 15–Feb 3 | 43,186 | 10.7M | 1,622 | **0.04x** | $32.72 |

**Opus accounts for ~93% of total cost ($35.30 total).**

### The 0.04x output ratio signal

Opus was consuming massive context (mostly cache reads) while producing almost no output. This is the signature of **exploration/research subagents** (Explore, general-purpose) running on Opus — they read lots of code but return a brief summary. These tasks don't need Opus-level capability.

Correct pattern: set `model: haiku` or `model: sonnet` in agent definitions for read-heavy, low-generation tasks (like the `quality-checker` agent already does).

### Activity patterns

- **Peak hours**: 20:00–23:00 (evening-only usage)
- **Most active project**: `pullscope` — 24 sessions, 126 messages (browser extension)
- **Avg session length**: 4.2 messages — many short one-off queries
- **Avg session duration**: 21 min

### Cache efficiency

Both models show 89–92% cache hit rates — the prompt cache is working well. This is the primary cost mitigation already in place.

---

## Optimization Principles

### 1. Match model to task
- **Haiku**: agents that only run bash commands and summarize (quality checks, stats, formatting)
- **Sonnet**: default for most tasks — good reasoning at reasonable cost
- **Opus**: reserve for truly complex reasoning tasks where quality matters

Always specify `model: haiku` or `model: sonnet` in agent frontmatter for non-reasoning tasks.

### 2. Watch the output/input ratio
A ratio below 0.1 on an expensive model means you're paying Opus prices for Haiku-level work. If you see this in `/usage` output, look at which agents were active that day.

### 3. Short sessions are fine, but...
With avg 4.2 msgs/session, repeated context-loading is likely happening. Project-level `CLAUDE.md` files with architecture context reduce how much the model needs to re-explore the codebase each session.

### 4. Stats cache lag
`stats-cache.json` may be days behind. For current-session analysis, parse `history.jsonl` directly (it's real-time). The `/usage` skill covers both.

---

## Approximate Pricing Reference (as of early 2026)

| Model | Input ($/MTok) | Output ($/MTok) | Cache read ($/MTok) | Cache write ($/MTok) |
|---|---|---|---|---|
| Haiku 4.5 | 0.80 | 4.00 | 0.08 | 1.00 |
| Sonnet 4.5/4.6 | 3.00 | 15.00 | 0.30 | 3.75 |
| Opus 4.5/4.6 | 15.00 | 75.00 | 1.50 | 18.75 |

Output tokens are 5x the input price — minimize unnecessary verbosity in agent prompts.
