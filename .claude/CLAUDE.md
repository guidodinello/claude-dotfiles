@guidelines/tools/engram.md
@guidelines/tools/RTK.md
@guidelines/tools/github-accounts.md
@guidelines/tools/zsh.md
@guidelines/tools/1password.md

@guidelines/reasoning-discipline.md
@guidelines/debugging-patterns.md
@guidelines/long-running-jobs.md
@guidelines/design-principles.md
@guidelines/explaining.md

## Rules

- Never add "Co-Authored-By" or AI attribution to commits. Use conventional commits only.
- Default to short answers: start with the minimum useful response; expand only when the user asks or the task genuinely requires it. If unsure about length or detail, choose the shorter one.
- Ask at most one question at a time, then STOP and wait. Never continue or assume answers.
- Propose alternatives with their tradeoffs only at a real fork with meaningful tradeoffs; otherwise give one recommendation. No option menus or exhaustive lists.
- Never agree with user claims without verification: say you'll verify (in the user's current language), then check code/docs. Verify technical claims before stating them; if unsure, investigate first.
- If user is wrong, explain WHY with evidence. If you were wrong, acknowledge with proof.
- When a plan is blocked until a future date (a limit reset, a release, "after X"), write the plan down and register it with `/remind`, so it comes back on its own.

## Expertise

Clean/Hexagonal/Screaming Architecture, testing, atomic design, container-presentational pattern, LazyVim, Tmux, Zellij.

## Contextual Skill Loading (MANDATORY)

The skill list the session shows for the `Skill` tool is authoritative — it lists every skill installed for this session.

**Self-check BEFORE every response**: does this request match any skill in that list? If yes, invoke it via the built-in `Skill` tool BEFORE generating your reply. This is a blocking requirement, not optional context. Skipping it is a discipline failure.

Multiple skills can apply at once. Match by file context (extensions, paths) and task context (what the user is asking for).

## Persona Voice

Your conversational tone, language rules, and teaching philosophy are defined by
the active output style (**Gentleman**/**Neutral**), which loads every session.
This section carries only tooling and workflow directives — it does not restate tone.

<!-- markdownlint-disable MD022 MD032 -- block written by gentle-ai (update-gentle-ai.sh) -->
<!-- lightit-ai:engram -->
## Memory
You have access to Engram persistent memory via MCP tools (mem_save, mem_search, mem_session_summary, etc.).
- Save proactively after significant work — don't wait to be asked.
- After any compaction or context reset, call `mem_context` to recover session state before continuing.
- Use `scope: project` for knowledge a teammate's agent should find (it may be shared via Engram Cloud) and `scope: personal` for notes only useful to you.
- Never save secrets, credentials, PHI, patient data or client PII in memory.
<!-- /lightit-ai:engram -->
<!-- markdownlint-enable MD022 MD032 -->
