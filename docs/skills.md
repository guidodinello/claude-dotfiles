# Skills

Slash-command skills available in Claude Code via `/skill-name`.

## Default enablement (`skillOverrides`)

Claude Code's skill picker (`Esc Esc` → Skills, or shown at session start) lets you toggle
each skill between `on` / `name-only` / `user-only` / `off` — but that toggle is **session-scoped
only**. It resets every session unless persisted via the `skillOverrides` key in
`~/.claude/settings.json` (this repo's committed, symlinked file — see
[Plugins, LSP & MCP guide § Settings scope](plugins-lsp-mcp-guide.md#settings-scope-what-actually-persists-where)
for why there's no per-machine-only variant of this).

```json
{
  "skillOverrides": {
    "clickup-create-ticket": "off",
    "hipaa-audit": "user-invocable-only"
  }
}
```

Values (per the settings schema):

| Value | Model sees name+description | `/skill-name` works | Use for |
|---|---|---|---|
| `on` (default, key absent) | Yes | Yes | Skills you want Claude to trigger autonomously |
| `name-only` | Name only, no description | Yes | Rarely used — cuts listing cost while keeping loose autodiscovery |
| `user-invocable-only` | No | Yes | Niche/client-specific skills (ClickUp, Slite, industry-specific audits) you invoke deliberately but don't want Claude guessing at |
| `off` | No | No | Skills you never want, even manually (deprecated/vendored duplicates, meta-skills that self-improve other skills) |

`off` and `user-invocable-only` cost the same **zero** standing tokens — neither goes into
the per-turn skill listing. The only difference is whether `/skill-name` still works. Default
to `user-invocable-only` unless you genuinely never want the manual escape hatch.

Current baseline (see `~/.claude/settings.json`): ClickUp/Slite sync skills and the
`meta-skill-*` self-improvers are `off`; audit skills (`hipaa-audit`, `security-audit`,
`db-scalability-audit`, `permissions-audit`, `code-health`, etc.) and PR/permissions helpers
are `user-invocable-only` since they're expensive/niche but still useful on demand.

| Skill | Description |
|---|---|
| `/address-pr-comments` | Fetches unresolved PR review threads, fixes valid ones, commits and pushes, then replies |
| `/audit-consolidation-validator` | Validates and repairs a client-facing consolidated audit document against internal audit files |
| `/audit-fact-checker` | Verifies reported audit findings against the actual codebase to confirm real bugs vs. false positives |
| `/clean-permissions` | Generalizes overly-specific Bash permission rules in settings files |
| `/clickup-create-ticket` | Creates Bug/Improvement/Task tickets in ClickUp for the active project |
| `/clickup-task-description` | Writes a QA-oriented ClickUp subtask description for completed backend work |
| `/code-health` | Codebase readiness audit: type safety, dead code, test coverage, complexity, deps |
| `/conventional-commits` | Generates granular conventional commits from staged changes |
| `/db-migration-planner` | Plans a database migration between providers with schema and data steps |
| `/db-scalability-audit` | Database scalability & architecture audit with provider-specific limits |
| `/figma-to-tailwind` | Implements UI components from Figma designs using Tailwind 4 + tailwind-variants |
| `/git-brag` | Finds your commits on a path, formatted for perf-review docs |
| `/hipaa-audit` | HIPAA Security Rule compliance audit for healthcare codebases |
| `/improve-codebase-architecture` | Surfaces architectural friction and proposes deepening opportunities — refactors that turn shallow modules into deep, testable, AI-navigable ones † |
| `/markdown-to-slite` | Syncs a local Markdown file to a Slite document (local file is source of truth) |
| `/meta-skill-db-scalability-audit-improver` | Refreshes provider limits and anti-patterns in the db-scalability-audit skill |
| `/meta-skill-hipaa-audit-improver` | Refreshes regulatory guidance and enforcement cases in the hipaa-audit skill |
| `/meta-skill-security-audit-improver` | Refreshes OWASP, CWE Top 25, and NIST guidelines in the security-audit skill |
| `/permissions-audit` | Comprehensive authorization audit across roles, permissions, and auth logic |
| `/qa-check` | Runs type-check, linting, and tests via the quality-checker subagent (stack-agnostic) |
| `/security-audit` | Application security audit covering OWASP Top 10 vulnerability patterns |
| `/slite-compare-docs` | Compares two Slite documents to check whether one fully supersedes the other |
| `/slite-to-clickup` | Syncs a Slite document to a ClickUp Doc page (Slite is source of truth) |
| `/ticket-refinement` | Writes and refines subtasks for software tickets (endpoints, components, APIs) |
| `/token-report` | Token usage report from Claude Code stats |
| `/write-tests` | Writes tests from a spec-driven philosophy: tests as executable specifications, behavior not implementation |
| `/writing-react-effects` | Reviews/writes React components to eliminate unnecessary useEffect usage |
