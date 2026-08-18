# The guideline system

How shared coding guidelines get from this repo into the projects that use them, why
the design is shaped the way it is, and the conventions to follow when adding a new one.

If you only read one thing: **the global copy in this repo is the source of truth, and
`push-guidelines.sh` is how projects get updates.** Editing a guideline inside a project
means running `promote.sh` first, or the next push overwrites it.

---

## The problem this solves

A guideline is useful in proportion to how many projects follow it, which means it has to
live in one place and be readable from many. Three constraints fight each other:

1. **Claude Code can import from an absolute path.** `@~/.claude/guidelines/python.md`
   works, and because `~/.claude/guidelines/*.md` are symlinks into this repo, the
   imported file can never drift. This is the cheapest option and the default.
2. **But remote Claude web sessions and other machines have no `~/.claude/`.** They see
   only the git checkout. An absolute home path resolves to nothing there.
3. **And symlinks don't survive `git clone`.** So "just symlink the guideline into the
   repo" doesn't travel either.

There is a fourth constraint that makes option 1 riskier than it looks. An import whose
path resolves outside the working directory is an **external import**, and Claude Code
gates those behind a one-time approval dialog:

> The first time Claude Code encounters external imports in a project, it shows an
> approval dialog listing the files. If you decline, the imports stay disabled and the
> dialog doesn't appear again.
> — [Claude Code docs: memory](https://code.claude.com/docs/en/memory)

Decline once and that project silently stops receiving its guidelines, with no error and
no second prompt.

So a repo that needs its guidelines to be reliably present — in cloud sessions, on a
colleague's machine, after a fresh clone — has to **commit its own copy**. Committed
copies are a second source of truth, and second sources of truth drift. Hence
`push-guidelines.sh`.

---

## The two consumption models

Pick per project, not per guideline.

### Model A — user-level rules, no wiring at all (default)

Nothing in the project. A path-scoped rule in `~/.claude/rules/` (symlinked from this
repo) fires whenever Claude touches a matching file, in **every** project on the machine.

Zero drift risk, zero per-project setup, and no external-import approval dialog. This
replaced the old `@~/.claude/guidelines/python.md` import convention, which required
remembering to wire each repo and silently broke if the approval dialog was ever declined.

Applies to: every project on this machine.

### Model B — commit a copy into the repo

The repo carries `.claude/rules/python.md` as a committed file, frontmatter and all. It
self-scopes exactly like the user-level copy, so **no import line is needed** — the file
being present in the repo is the whole wiring.

Required when the project must work in a remote Claude web session, in CI, on another
machine, or for a teammate. Costs a sync step — that's what `push-guidelines.sh` is for.

**A Model B repo must also exclude the user-level copies, or both load.** On a machine
that has this repo, the user-level rule and the committed rule both match the same file
and both get pulled into context — measured, and it duplicated all 914 lines of
`python.md`. Add to the project's `.claude/settings.json`:

```json
{
  "claudeMdExcludes": [
    "**/claude-dotfiles/.claude/rules/**",
    "**/claude-dotfiles/.claude/guidelines/**"
  ]
}
```

The `Project` copy then wins, which is the right outcome: local behavior matches what a
cloud session sees, since the committed file is the only one that exists there. The glob
is path-based rather than absolute, so it's harmless on machines without this repo.

Currently: `fitted` only.

---

## The three sync directions

| Direction | Script | When |
|---|---|---|
| this repo → `~/.claude/` | `sync.sh` | after `git pull`, or a new machine |
| a project → this repo | `promote.sh` | a project-local file is good enough to go global |
| this repo → projects | `push-guidelines.sh` | refresh the committed copies of Model B repos |

**Edited a guideline inside a project? `promote.sh` first, then `push-guidelines.sh`.**
Pushing first overwrites your edit with the older global version. This is the single
easiest thing to get wrong.

`push-guidelines.sh` is dry-run by default and safe by construction:

- **`--existing`** — only refreshes files the project already has. A project's *file set*
  is its own choice (adopting a new guideline is a deliberate `cp`); the *content* is
  owned by this repo. Without this, `php.md` would land in a Node repo.
- **no `--delete`** — project-specific files sitting in the same directory survive.
- **`-c`, and deliberately no `-t`** — these are a matched pair. `-t` would make
  byte-identical files report attribute-only drift, so every dry run cries wolf; dropping
  `-t` leaves destination mtimes newer than source, so without `-c` rsync's default
  size+mtime check re-copies everything every run. Change one and the other breaks.

---

## Global vs project-specific content

A guideline promoted out of a project is almost never generic on arrival. The split:

**Global file** (`.claude/guidelines/<topic>.md`) — the rule, the reasoning, and the
failure shape. Neutral placeholders (`myapp`, `app`) instead of real project names. No
links to a specific repo's PRs. Examples may stay in one language when that reflects
reality, but say so in the opening paragraph rather than letting the reader assume.

**Project-specific content** — the workflow table, the service topology, the runner
mapping, the incident history. This lives in the **folder's own doc**, next to the code it
describes. See the convention below.

> **Do not create `<topic>-<project>.md` sibling files.** This was the original plan and
> it was wrong: the per-directory `CLAUDE.md` / `README.md` already owns that content, so
> a sibling file manufactures a second source of truth for the same facts — the exact
> problem `push-guidelines.sh` exists to prevent. Check whether the split already exists
> under a different name before inventing a new file.

The rule of thumb: **if removing it from the global file would make another project's
copy wrong, it was project-specific. If it would make the rule unmotivated, keep it.** A
merge-semantics rule with no motivating failure is the paragraph people skim — so keep the
failure *shape* global and move only the "we hit this in PR #294" attribution.

---

## Per-folder convention

Guidelines are only worth loading when Claude is actually working in the area they cover.
Claude Code supports this directly:

> Claude also discovers `CLAUDE.md` and `CLAUDE.local.md` files in subdirectories under
> your current working directory. Instead of loading them at launch, they are included
> when Claude reads files in those subdirectories.
> — [Claude Code docs: memory](https://code.claude.com/docs/en/memory)

So a folder that has its own conventions gets two files:

```
.claude/rules/ci.md          # shared, synced from this repo, self-scoping — no import
.github/
  README.md                  # what's in this folder + this project's CI specifics
  CLAUDE.md                  # @README.md
```

The shared guideline needs **no import line at all** — it's a path-scoped rule, so it
loads on its own when Claude touches a matching file. `CLAUDE.md` exists only to pull in
the folder's README. Why this shape:

- **`README.md` holds the substance** because GitHub renders it automatically in the
  directory listing. `CLAUDE.md` is invisible to everyone except Claude. One file, three
  audiences: humans browsing the repo, the GitHub web UI, and remote Claude sessions.
- **Never copy the shared file into the folder.** `push-guidelines.sh` discovers targets
  by globbing `*/.claude/{rules,guidelines}/`, so a copy anywhere else would never be
  refreshed and would drift immediately.
- **`CLAUDE.md` may add agent-only lines below the import.** README and CLAUDE.md don't
  have identical audiences: "never run `docker build` on the VPS" reads fine in a README,
  but "delegate to the product-manager agent" doesn't. Shared substrate in README,
  agent-directives appended in CLAUDE.md.

An always-on guideline from `.claude/guidelines/` still needs an explicit
`@../.claude/guidelines/<topic>.md` import here — that's the difference between the two
directories in practice.

Import mechanics worth knowing: relative paths resolve against the file containing the
import, imports nest up to four hops, and **import parsing skips code spans** — so
`` `@README` `` in backticks is literal text, while `@README` imports.

### The compaction caveat

Scoping has a real cost:

> Nested CLAUDE.md files in subdirectories and rules with `paths:` frontmatter are not
> re-injected automatically [after `/compact`]; they reload the next time Claude reads a
> file in that subdirectory.

Root `CLAUDE.md` survives compaction; a nested one does not. If a long session compacts
mid-task, the folder's guideline is gone until Claude touches a file there again. Put
anything that must hold for the whole session in the root `CLAUDE.md`, and treat nested
files as *area* context rather than *invariant* context.

---

## Rules vs guidelines

There are two shared-content directories, and the split is by **how the content loads**,
not by what it covers.

| | `.claude/rules/` | `.claude/guidelines/` |
|---|---|---|
| Loads | only when Claude touches a file matching `paths:` | always, via an explicit `@` import |
| Scoping | glob, layout-independent | whole session |
| Audience | agent only | agent only |
| Holds | docker, ci, python, php, database | reasoning-discipline, debugging-patterns, client-issue-workflow, tools/*, react-native |

**Default to a rule.** A guideline that only matters when editing a certain kind of file
shouldn't burn context on every unrelated session. Use `guidelines/` only for content that
genuinely applies regardless of what you're touching.

A rule is a normal markdown file with YAML frontmatter:

```markdown
---
paths:
  - "**/Dockerfile*"
  - "**/docker-compose*.yml"
---
```

### Why the globs are layout-independent

This was the one thing that looked like it would block the whole approach — surely the
`paths:` list is project-specific while the body is global, so any sync would clobber the
frontmatter? Measured across the real repos, it isn't:

| Rule | Real locations | Glob |
|---|---|---|
| docker | `knowledger/Dockerfile` (root), `fitted/docker/backend/Dockerfile.dev` (3 deep), `url-shortener/backend/Dockerfile.production` (2 deep) | `**/Dockerfile*` |
| ci | `.github/workflows/` in 8 repos | `.github/workflows/**` |
| python | `.py` everywhere | `**/*.py` |
| database | `fitted/backend/alembic/`, `php/*/database/migrations/` | `**/alembic/**`, `**/migrations/**` |

Depth varies wildly, and `**/` absorbs exactly that. So frontmatter and body are both
global, and `push-guidelines.sh` syncs the whole file with no special handling.

### `~/.claude/rules/` — the big win

User-level rules **apply to every project on the machine**, with no per-project wiring at
all. `sync.sh` symlinks the whole `.claude/` tree, so anything added to
`claude-dotfiles/.claude/rules/` deploys to `~/.claude/rules/` automatically.

This is why the Model A `@~/.claude/guidelines/python.md` imports were retired: a project
touching a `.py` file now gets `python.md` regardless of whether anyone remembered to wire
it up. It also sidesteps the external-import approval trap entirely, because rules are not
imports. Repos that never had a CLAUDE.md at all — `url-shortener`, `rl-tournament-notification-bot`
— started receiving guidance the moment the rules directory existed.

The limit is the familiar one: user-level rules are machine-local. They don't reach cloud
sessions or teammates, so Model B repos still commit their own `.claude/rules/`.

### When a rule doesn't fit

`react-native.md` stayed a guideline. React Native and web React share `.tsx`, so any glob
wide enough to catch RN components also fires on the 83 web components in
`fitted/frontend/web/` — and `fitted/frontend/mobile/` has no `.tsx` files or
`metro.config.js` to target instead, since the app isn't built yet. It's folder-scoped by
`frontend/mobile/CLAUDE.md` instead.

**If a guideline can't be cleanly glob-scoped, that's a signal — don't force a wide glob.**
A rule that fires on the wrong files is worse than one that loads a bit too often.

---

---

## Verifying a rule actually fires

Don't assume a glob works — watch it. The `InstructionsLoaded` hook reports every
instruction file as it loads, and its `path_glob_match` reason is exactly a path-scoped
rule triggering. Drop this in a throwaway project's `.claude/settings.json`:

```json
{
  "hooks": {
    "InstructionsLoaded": [
      { "hooks": [ { "type": "command",
        "command": "cat >> \"$CLAUDE_PROJECT_DIR/loaded.jsonl\"; echo >> \"$CLAUDE_PROJECT_DIR/loaded.jsonl\"" } ] }
    ]
  }
}
```

Then drive it headlessly and read the log:

```bash
claude -p "Read foo.py and reply DONE." --allowed-tools Read --permission-mode acceptEdits
grep path_glob_match loaded.jsonl
```

The payload is richer than the docs describe — it names the rule, its globs, and what
triggered it:

```json
{
  "hook_event_name": "InstructionsLoaded",
  "load_reason": "path_glob_match",
  "memory_type": "User",
  "file_path": ".../claude-dotfiles/.claude/rules/python.md",
  "globs": ["**/*.py", "**/pyproject.toml"],
  "trigger_file_path": ".../foo.py"
}
```

`memory_type` is `User` for `~/.claude/rules/` and `Project` for a committed
`.claude/rules/` — which is how the double-load above was caught. Always include a
**negative control**: read a file no rule should match and confirm zero
`path_glob_match` events. A rule that fires on everything looks identical to a rule that
works until you check.

Two behaviors worth knowing, both measured rather than documented:

- **Glob matching is case-insensitive.** `**/models/**` matches `app/Models/User.php`.
- `load_reason: "include"` events count the always-on `@` imports — six of them here,
  matching the six files imported by `~/.claude/CLAUDE.md`. A quick sanity check that
  the always-on set is what you think it is.

---

## Reaching other agents (opencode)

Everything above is Claude Code machinery. Path-scoped rules with `paths:`
frontmatter are a Claude Code feature; opencode does **not** read
`.claude/rules/` at all. opencode does load `~/.claude/CLAUDE.md` as global
instructions by default, but it does **not** resolve `@` imports inside it —
so inline guidance reaches opencode, while `@`-imported guideline bodies
don't.

opencode has its own conventions, and the bridge between the two is a
*loading index* rather than a format conversion:

| Concern | Claude Code | opencode |
|---|---|---|
| Always-on global guidance | `~/.claude/CLAUDE.md` + `@` imports | `AGENTS.md` / `CLAUDE.md` fallback, or the `instructions` key in `opencode.json` |
| Path-scoped rules | `.claude/rules/<topic>.md` with `paths:` frontmatter | none (per-directory `AGENTS.md` is the closest) |

### How the bridge works

`.config/opencode/rules-index.md` is a small always-loaded file (wired via
`"instructions": ["~/.config/opencode/rules-index.md"]` in
`.config/opencode/opencode.jsonc`) that:

1. tells opencode the rules exist and must be lazy-loaded — read a rule file
   only when the task touches a matching path, and treat it as mandatory;
2. lists every rule as a table row: rule name, file path, the globs it
   scopes to, and when to load it.

The bodies stay out of context until needed — same economics as path
scoping, but enforced by instruction instead of mechanism. The index must
stay small and current; add a row when you add a rule.

### Deployment and gotchas

- `sync.sh` symlinks the whole `.config/opencode/` tree, so the index and
  the `instructions` key deploy to every machine like the rest of this repo.
- `instructions` paths resolve from the **project directory**, not the
  config directory (verified empirically). A relative path in the global
  config only resolves if the file happens to exist in the project — use the
  `~` absolute form, which always resolves.
- Instruction files are injected at session start without permission gating;
  what the permission system gates is the model's later lazy `Read` of the
  rule files. Keep the index inside `~` (`.config/opencode/`) so both work
  from any project dir.
- `opencode.json` and `opencode.jsonc` in the same config dir are **merged**,
  not mutually exclusive — but the merge replaces array keys (including
  `instructions`) rather than combining them. Keep machine-specific config in
  the untracked `.json` and shared config in the tracked `.jsonc`, and define
  each array-valued key in exactly one of them.

Verify a change the same way the rules themselves are verified: run
`opencode run "list the rules in your instructions"` from a project dir and
confirm the model sees the index — and that a follow-up read of a rule file
succeeds.

---

## Adding a new guideline

1. **Default to a rule.** Write it in `.claude/rules/<topic>.md` with `paths:`
   frontmatter scoping it to the files it's about. Generic from the start is
   easier than genericizing later — see below. Only use
   `.claude/guidelines/<topic>.md` (no `paths:`, always-on) for content that
   genuinely applies regardless of what file is being touched.
2. `./sync.sh` to symlink it into `~/.claude/rules/` (or `~/.claude/guidelines/`).
   Rules apply to every project on this machine immediately — no per-project
   wiring. A guideline still needs an explicit `@~/.claude/guidelines/<topic>.md`
   import (Model A) or a committed copy imported relatively (Model B) in each
   project that should follow it.
3. Document it in [`guidelines.md`](guidelines.md).
4. If it's a rule, add a row to the opencode index
   (`.config/opencode/rules-index.md`) with the same globs — the index is
   the only way opencode loads rules, so a rule without a row never reaches
   it.

## Promoting one out of a project

`promote.sh` moves the file and symlinks it, but **it does not genericize.** That step is
manual and easy to skip — it was skipped for `ci.md` and `docker.md` in commit `b258648`,
which left fitted's project name, repo layout, service topology and PR links sitting in
the global library for months while other projects imported them.

So after `promote.sh`, before telling anyone the guideline is global:

```bash
grep -Eic '<project-name>|this project|<internal-image>|<internal-job-names>' \
  .claude/guidelines/<topic>.md
```

Expect `0`. Then check for the things grep can't see — repo-relative paths
(`../backend/src`), service names, port numbers, and hardcoded version pins that nothing
will ever update.

<!-- The 0.6.14 uv pin sat stale in the global docker.md while fitted ran 0.7.2 and
     knowledger ran 0.11.29 — hence the <version> placeholder convention. -->
