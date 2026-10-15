# Per-project docs folder template

Layout, following the `dev-docs-index` convention (every folder has a `README.md`):

```
release-sim/
  README.md          index + project profile
  data-shapes.md     catalog of prod-like shapes, creation snippets, lessons
  runs/
    README.md        index of runs
    YYYY-MM-DD-<change>.md
    assets/<run-name>/NN-description.png   (optional)
```

## README.md

```markdown
# Release simulation: <project>

Profile and index for local release simulations of <project>. Method: the `release-sim` skill.

## Documents

| File | What it covers |
|---|---|
| `data-shapes.md` | Prod-like data shapes, how to create each, lessons |
| `runs/README.md` | One doc per simulation run |

## Profile

- **Prod ref**: <which ref prod runs, and how to find it (tag, deploy config, command)>
- **Next-release ref**: <branch/tag>
- **Repos involved**: <repos; which one(s) get the sim worktree>
- **Worktree location**: <default: sibling of the product repo; must not land inside a tracked tree>
- **Migrations path**: <path>
- **Bring up an isolated stack**: <command, always with `-p relsim-<slug>`>
- **Port overrides**: <env var = chosen value, per forwarded port: app, DB, Redis, mail UI, ...>
- **Migrate command (deploy-like, non-interactive, forced)**: <command>
- **Seed command**: <command>
- **Shape-creation mechanism**: <tinker/REPL script, seeder class, or SQL against the sim DB only>
- **Login (synthetic seeded account)**: <email placeholder / how to obtain>
- **Stop the stack**: <command, only the relsim project>
```

## data-shapes.md

```markdown
# Data shapes

Synthetic shapes that mirror what prod has. Never real records.

## <Domain>

### <Shape name>

- **Why prod has it**: <one line, with source>
- **Create it**:

  <snippet in the profile's mechanism>

- **Lessons**: <date, what went wrong or was learned, link to the run doc>
```

## runs/README.md

```markdown
# Runs

| Run | Change | Prod / next / PR SHAs |
|---|---|---|
| `YYYY-MM-DD-<change>.md` | One line | short SHAs |
```

## runs/YYYY-MM-DD-change.md

```markdown
# <change>: release simulation, YYYY-MM-DD

## Refs

- Prod: <full SHA> (<ref name>)
- Next release: <full SHA> (<ref name>)
- PR head: <full SHA> (<PR>) or none

## Setup

- Compose project: relsim-<slug>
- Ports used: <env var = value>
- Warnings: <e.g. `gh` unavailable, hotfix check partial>

## Results

| Shape | Release without fix | Release with fix | Re-run |
|---|---|---|---|
| <shape> | <result> | <result> | <unchanged / changed> |

## Screenshots

<optional: runs/assets/<run-name>/NN-description.png>

## Lessons

<new lessons, also folded into `data-shapes.md`>
```
