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
    "meta-skill-hipaa-audit-improver": "off",
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

Current baseline (see `~/.claude/settings.json`): Slite sync skills and the
`meta-skill-*` self-improvers are `off`; audit skills (`hipaa-audit`, `security-audit`,
`db-scalability-audit`, `permissions-audit`, `code-health`, etc.) and PR/permissions helpers
are `user-invocable-only` since they're expensive/niche but still useful on demand.

| Skill | Description |
|---|---|
| `/accessibility-review` | WCAG 2.2 AA audit of the web frontend (semantic HTML, ARIA, keyboard, contrast, screen readers, reduced motion, touch targets), grouped by component; applies only safe, unambiguous fixes |
| `/address-pr-comments` | Fetches unresolved PR review threads, fixes valid ones, commits and pushes, then replies |
| `/api-gap-audit` | Diffs backend route definitions against frontend API call sites and classifies each gap; may write issue stubs, never edits existing code |
| `/async-audit` | Detects and fixes bad sync/async usage in a Python backend: blocking calls in async handlers, fire-and-forget tasks, missing ruff ASYNC rules |
| `/audit-consolidation-validator` | Validates and repairs a client-facing consolidated audit document against internal audit files |
| `/audit-fact-checker` | Verifies reported audit findings against the actual codebase to confirm real bugs vs. false positives |
| `/babysit-prs` | Orchestrates every open PR toward merge: CI runner health, failed-run triage, conflict resolution, herdr Sonnet `/code-review` (`spawn_reviewer.py`), `address-pr-comments` dispatch, auto-merge. Needs an interactive herdr session |
| `/backward-trace` | First-principles investigation method for how a mechanism actually works; required pre-step before changing shared or cross-cutting behavior |
| `/clean-permissions` | Generalizes overly-specific Bash permission rules in settings files |
| `/client-issue-workflow` | Handles a client-reported bug: acknowledge, investigate, explain neutrally, then fix or present options |
| `/code-health` | Codebase readiness audit: type safety, dead code, test coverage, complexity, deps |
| `/code-review` | Multi-agent PR review with confidence scoring (CLAUDE.md compliance, bugs, git history, previous PR comments); posts blocking and non-blocking findings on the PR |
| `/configure-dependency` | Fetches official docs and configures a new package, service, or external integration correctly from the start |
| `/conventional-commits` | Generates granular conventional commits from staged changes |
| `/db-migration-planner` | Plans a database migration between providers with schema and data steps |
| `/db-scalability-audit` | Database scalability & architecture audit with provider-specific limits |
| `/design-review` | High-level, ADR-shaped review of a PR: decisions and rejected alternatives, quality attributes, trade-offs, invariants and their guards, risks checked against a cited principle catalog. Read-only |
| `/dev-docs-index` | Conventions for a repo's `my-dev-things/` knowledge base: a README index in every folder, inline source citations, and tree-first navigation |
| `/discover-conventions` | Surfaces de-facto conventions the code follows but nobody wrote down, and proposes ADR drafts, CLAUDE.md additions, and convention index entries |
| `/figma-snapshot` | Snapshots Figma pages, sections or frames via the REST API (2x PNGs, flow, designer notes, exact copy) and re-renders only what changed; cheap `check` for design updates |
| `/find-session` | Finds past Claude Code sessions by remembered keywords (TF-IDF ranked) and gives the resume command; `--pick` opens an fzf picker |
| `/fix-ignores` | Audits lint and type suppression comments (Python and TypeScript) and fixes the underlying issues so the suppressions can be removed |
| `/git-brag` | Finds your commits on a path, formatted for perf-review docs |
| `/hipaa-audit` | HIPAA Security Rule compliance audit for healthcare codebases |
| `/improve-codebase-architecture` | Surfaces architectural friction and proposes deepening opportunities — refactors that turn shallow modules into deep, testable, AI-navigable ones † |
| `/in-worktree` | Runs another skill inside an isolated git worktree (fresh branch or an existing PR branch) so parallel tools and tasks do not touch each other's files |
| `/ios-sim` | Verifies web UI in real iOS Safari in the Xcode Simulator (viewport units, safe areas, Safari toolbar), measured base vs PR, with a per-project docs folder |
| `/markdown-to-slite` | Syncs a local Markdown file to a Slite document (local file is source of truth) |
| `/meta-skill-db-scalability-audit-improver` | Refreshes provider limits and anti-patterns in the db-scalability-audit skill |
| `/meta-skill-hipaa-audit-improver` | Refreshes regulatory guidance and enforcement cases in the hipaa-audit skill |
| `/meta-skill-security-audit-improver` | Refreshes OWASP, CWE Top 25, and NIST guidelines in the security-audit skill |
| `/model-frontier` | Picks model and effort per role from the Artificial Analysis Intelligence Index (every effort level, cost vs intelligence plot) and measures past changes on our own transcripts |
| `/my-voice` | Drafts messages in Guido's voice (global rules + project audience file + sent corpus) and turns his wording corrections into rules |
| `/opencode-dual-review` | Deprecated, opt-in: free second-opinion PR review: two opencode models post untriaged inline-comment reviews, with a Sonnet medium-effort fallback |
| `/orca-orchestration` | Lands a story's subtasks through Claude Code implementer sessions in Orca worktrees: plan approval, transcript supervision, review and merge waves, with a per-project docs folder |
| `/permissions-audit` | Comprehensive authorization audit across roles, permissions, and auth logic |
| `/qa-check` | Runs type-check, linting, and tests via the quality-checker subagent (stack-agnostic) |
| `/react-composition-audit` | Audits React code for defects linters miss: hand-rolled markup duplicating a design-system primitive, and wrong element/ARIA semantics |
| `/recap` | Rebuilds your GitHub, git, ClickUp, Slack and engram activity for a day or range, grouped by ticket, for standups |
| `/release-sim` | Simulates a release locally (prod ref → next ref, optionally a fix PR) with synthetic data shapes to catch migration/backfill bugs; per-project docs folder holds shapes and lessons |
| `/sandbox-diff` | Verifies a backend PR that touches a vendor integration by running base and PR code on the same vendor-sandbox data: a fail-closed safety gate before any write or send, scoped write scripts, time simulation, a mutation check, and tables that claim only what ran; per-project docs folder holds the profile and scenarios |
| `/scripts-audit` | Checks that every file under `scripts/` is documented in `scripts/CLAUDE.md` and every documented script still exists. Report only |
| `/security-audit` | Application security audit covering OWASP Top 10 vulnerability patterns |
| `/slite-compare-docs` | Compares two Slite documents to check whether one fully supersedes the other |
| `/system-integration-map` | Clickable two-level map of a system: every external integration and internal process, each arrow labeled with direction and mechanism and linked to its code, plus traceable flows. Built from code by parallel explorers |
| `/test-health` | Read-only test-suite audit against T1–T40: proves each harness (network/console guards, random order, retries, merged coverage) covers what it claims, then ranks tests that can't fail and nondeterminism above smells |
| `/ticket-refinement` | Writes and refines subtasks for software tickets (endpoints, components, APIs) |
| `/type-health` | Audits and improves type coverage: Python backend (Pydantic at IO boundaries), TypeScript frontend (Zod-first), TypeScript backend (NestJS/TypeORM) |
| `/ui-ux-review` | Evaluates UI/UX quality (flow, visual consistency, layout, copy, interaction) from a screenshot, recording, or component path. Findings only |
| `/worktree-bootstrap` | Per-repo Orca setup and archive scripts that source a shared helper lib: isolated compose project and ports per worktree, env files copied, deps installed, workspace `CLAUDE.md` and notes linked; with a self-check |
| `/write-tests` | Writes tests from a research-backed philosophy (T1–T40, shared with `/test-health`): behaviour over implementation, doubles only at real boundaries, deterministic, and each test seen failing once |
| `/writing-react-effects` | Reviews/writes React components to eliminate unnecessary useEffect usage |
