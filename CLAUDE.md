# Claude Dotfiles

This repo is the source of truth for `~/.claude/` and `~/.agents/` — skills, agents, hooks, and settings scaffolded globally across machines.

## Skills vs Agents

**Skills** (`.claude/skills/`) are guidance documents for Claude — invoked via `/skill-name`. They contain instructions, methodology, and reporting format. Claude reads them and executes the steps itself.

**Agents** (`.claude/agents/`) are subagents launched via the `Agent` tool. They run as separate processes with their own tool access and return a result. Use agents for I/O-heavy work that doesn't need complex reasoning (REST API calls, file transforms, running shell pipelines and summarizing output).

Rule of thumb: if the task is "call an API and write the result somewhere", it's an agent. If the task is "investigate a codebase and produce a structured report", it's a skill.

## The Delegate Pattern

Some skills exist solely to preprocess arguments and then spawn an agent. This is the right pattern when:
- The skill needs to validate/transform inputs before the agent runs (e.g. style rule enforcement, argument parsing)
- The agent is reusable across multiple skills

To implement: set `disable-model-invocation: true` in the skill's frontmatter if the skill itself does no reasoning — it's purely a launcher. Examples: `qa-check`, `token-report`.

If the skill does preprocessing (e.g. `markdown-to-slite` applies style rules before spawning `slite-sync`), do NOT set `disable-model-invocation: true`.

## Audit Skills

All audit skills share a common reporting structure. See `.claude/guidelines/templates/audit-template.md` for the shared contract: document header, findings format (severity IDs, dead code rule), remediation tiers, and key files reference. Each audit skill adds its own discovery steps and domain-specific violation patterns on top.

## Cross-Agent Skills (`.agents/skills/`)

`.agents/skills/` is a cross-agent standard maintained by Vercel Labs, recognized by Claude Code, Copilot, Cursor, Gemini CLI, and others. Skills installed here via `npx skills` are tracked in `skills-lock.json` (equivalent to `package-lock.json`).

This layer is separate from `.claude/` — don't put Claude Code-specific agents or slash-command skills here. Use it for ecosystem skills installable via `npx skills add <owner/repo>`.

To install a skill: `npx skills add <owner/repo>`
To update all skills: `npx skills update`

## Naming Conventions

- Skill directories: `kebab-case`, descriptive of what the skill does
- Sync skills: `source-to-destination` pattern (e.g. `markdown-to-slite`, `slite-to-clickup`)
- Agent model choice: use Haiku for I/O-bound tasks (API calls, file transforms, summarization); Sonnet when reasoning is needed
