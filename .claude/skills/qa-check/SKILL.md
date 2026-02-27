---
name: qa-check
description: Run the full quality pipeline (type-check, linting, tests) via the quality-checker subagent. Returns a concise summary of issues without flooding the main context with raw output.
disable-model-invocation: true
---

Delegate to the `quality-checker` subagent to run the full quality pipeline.

Do not run any commands yourself. Do not explain what you're about to do. Just invoke the subagent immediately and report back its summary.

Once the subagent returns, present its output as-is and ask if any of the failures should be fixed now.