## Reasoning discipline
Apply on any non-trivial task, especially before committing to an approach or declaring done.
- **Don't accept the offered options as the whole option space.** When handed a choice ("do A or B"), check what the framing excludes — the best answer is often a third option neither side named.
- **Verify claims against primary sources, not memory.** When a decision turns on how a tool/library/API behaves, read the actual source or official docs and quote it. Don't assert from recollection.
- **Name the done-signal before building.** State the observable check that will prove the work is right (a test, a command and its expected output, a screen state) before writing the change. A check chosen afterwards tends to be one the code already passes. If no check is possible, say so up front.
- **List the unknowns and how each gets resolved.** Before choosing an approach, write down what you don't know that would change it, and settle each one by reading the source, running a spike or asking the user. Don't build on a guess. Skip both steps for a trivial edit.
- **Verify empirically before declaring done.** Source-verified is not done — run it once and watch the expected signal. A passing self-test that doesn't check the real thing is not evidence.
- **One source of truth per fact.** When writing docs, memories, or config, link to the owner (Slite, code, another doc) instead of copying its content. A copy is a second source of truth, and second sources of truth drift.
- **Separate what's required from what was merely suggested.** Keep only the changes the goal actually needs; revert incidental edits back to pristine.
