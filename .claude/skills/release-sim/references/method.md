# Release simulation method

Placeholders in `<angle brackets>` come from the project profile (`README.md` in the docs folder). Commands are generic; use the profile's actual stack commands.

## 0. Resolve refs

```bash
PROD_SHA=$(git -C <repo> rev-parse <prod-ref>)
NEXT_SHA=$(git -C <repo> rev-parse <next-ref>)
PR_SHA=$(git -C <repo> rev-parse <pr-head>)   # only when a fix PR is under test
```

Tags and SHAs are preferred over branch names. Record all three in the run doc.

## 1. Hotfix check

```bash
git -C <repo> log --oneline $NEXT_SHA..$PROD_SHA
gh pr list --repo <owner/repo> --state open --search "base:<next-branch>" 
```

Code on prod that is missing from the next release changes what the simulation means. If anything shows up, stop and ask. If `gh` fails, continue with the `git log` result only and note the warning in the run doc.

Also diff the migrations path: no migration or backfill between prod and next means the simulation has nothing to catch.

```bash
git -C <repo> diff --name-only $PROD_SHA $NEXT_SHA -- <migrations-path>
```

## 2. Isolated worktree and stack

```bash
git -C <repo> worktree add --detach <worktree-path> $PROD_SHA
cd <worktree-path>
export COMPOSE_PROJECT_NAME=relsim-<change-slug>
# Override every forwarded host port with free ones (names from the profile):
export <APP_PORT_VAR>=<free-port> <DB_PORT_VAR>=<free-port> <REDIS_PORT_VAR>=<free-port>
```

- Check the chosen ports are free before starting (`lsof -iTCP:<port> -sTCP:LISTEN`).
- Check `docker compose ls` first: if a project with this name already exists and the skill did not start it, pick another name. Never reuse it.
- Bring the stack up with the profile's command, always passing `-p $COMPOSE_PROJECT_NAME`.
- Register teardown immediately so it runs on failure too (see step 9).

## 3. Fresh DB at the prod ref

Run the profile's migrate and seed commands. The sim DB is created empty here; never restore a dump.

## 4. Create the data shapes

Create each shape listed for this change the way prod has them, using the snippet stored in `data-shapes.md` (tinker/REPL script, seeder class, or SQL against the sim DB only). Synthetic records only.

## 5. Release without fix

```bash
git -C <worktree-path> checkout --detach $NEXT_SHA
# run migrations as a deploy would: non-interactive, forced (profile command)
```

Record the result per shape: this is the "release without fix" column. Capture the migration output and the resulting state of each shape's records.

## 6. Release with fix (only if a fix PR is under test)

```bash
git -C <worktree-path> checkout --detach $PR_SHA
# migrate again with the same command
```

Record per shape: the "release with fix" column. If the PR changes already-applied migrations, say so in the run doc.

## 7. Idempotency

Run the migration command again at the final ref. The per-shape state must not change. Record the outcome as the "re-run" column.

## 8. Report

Write `runs/YYYY-MM-DD-<change>.md` from the template: refs as SHAs, shapes used, the table, warnings, lessons. Screenshots are optional (`runs/assets/<run-name>/NN-description.png`, synthetic data only).

## 9. Teardown

Always, including on failure:

```bash
docker compose -p $COMPOSE_PROJECT_NAME down -v    # only the project this run started
git -C <repo> worktree remove --force <worktree-path>
```

Never `down` any other project. If a step failed, tear down first, then report the failure.

## Worked example: a data-shape gap

A clinic was first skipped by a backfill migration with "no active owner", because the simulation had created it without an owner (prod clinics always have one). The result looked like a migration bug but was a shape bug. The fix was to add an "owner present" shape to `data-shapes.md` with its creation snippet and re-run the migration. Lessons like this belong in the docs folder so the next run starts with them: when a result looks surprising, ask whether the shape is faithful to prod before blaming the code.
