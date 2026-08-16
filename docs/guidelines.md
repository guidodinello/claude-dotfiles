# Guidelines and rules

Reusable coding and workflow conventions. They live in two directories, split by **how
they load** — see [The guideline system](guideline-system.md) for the full rationale,
the sync directions, and the per-folder convention.

## `.claude/rules/` — path-scoped, load on demand

Each file carries `paths:` YAML frontmatter and is pulled into context only when Claude
touches a matching file. Symlinked into `~/.claude/rules/` by `sync.sh`, which makes them
apply to **every project on this machine with no per-project wiring**.

| File | Loads when touching |
|---|---|
| `rules/docker.md` | `**/Dockerfile*`, `**/*.dockerfile`, `**/docker-compose*.{yml,yaml}`, `**/.dockerignore` |
| `rules/ci.md` | `.github/workflows/**` |
| `rules/python.md` | `**/*.py`, `**/pyproject.toml` |
| `rules/php.md` | `**/*.php`, `**/composer.json` |
| `rules/database.md` | `**/alembic/**`, `**/migrations/**`, `**/*.sql`, `**/models/**` |

**This is the default home for a new guideline.** Something that only matters when editing
a certain kind of file shouldn't consume context in every unrelated session.

## `.claude/guidelines/` — always-on, imported explicitly

For content that applies regardless of which file is open. Imported by an `@` reference
from a `CLAUDE.md`.

| File | Use |
|---|---|
| `guidelines/reasoning-discipline.md` | Verify against primary sources; check the option space |
| `guidelines/debugging-patterns.md` | Fix-completeness verification in layers |
| `guidelines/client-issue-workflow.md` | How to handle a client-reported bug end to end |
| `guidelines/react-native.md` | React Native conventions — see note below |
| `guidelines/tools/engram.md` | Engram persistent-memory protocol |
| `guidelines/tools/RTK.md` | RTK token-optimizing CLI proxy |
| `guidelines/tools/github-accounts.md` | Two-GitHub-account setup (personal vs work) |
| `guidelines/templates/audit-template.md` | Shared reporting contract for the audit skills |

`react-native.md` is here not because it's always-on but because it **can't be cleanly
glob-scoped**: RN and web React share `.tsx`, so any glob wide enough to catch RN
components also fires on web ones. It's folder-scoped by `fitted/frontend/mobile/CLAUDE.md`
instead. If a guideline can't be glob-scoped, don't force a wide glob — a rule that fires
on the wrong files is worse than one that loads too often.

## Adding a new one

1. Decide: does it only matter for certain files? → `rules/` with `paths:`. Otherwise →
   `guidelines/`.
2. Write it, then `./sync.sh` to symlink it into `~/.claude/`.
3. Rules need no further wiring. Guidelines need an `@` import somewhere.
4. For repos that must work in cloud sessions, `cp` it into their `.claude/rules/` (or
   `.claude/guidelines/`) and let `push-guidelines.sh` keep it current.
