# Per-project docs folder template

Layout, following the `dev-docs-index` convention (every folder has a `README.md`):

```
harness/<topic>/
  README.md              profile, workflow, script index, scenario index
  scenarios/
    <change>.md          one per run (or per review round)
  scripts/               scoped write scripts, capture runners, run helpers
<write log>              per project, path named in the profile (e.g. setup/test-users.md)
```

## README.md (profile)

```markdown
# Harness: <topic>

Base-vs-PR runs of <area> against the <vendor> sandbox. Method: the `sandbox-diff` skill.
Local only; never committed to the product repo.

## Profile

- **Base ref**: <branch the PR targets>
- **Worktree stack**: <how a PR worktree comes up; services to start; services never to start (scheduler)>
- **Usable-stack checks**: <tables exist, API answers, no scheduler container>
- **Migrate**: <command>
- **Seed a test account locally**: <command>
- **Run PR code**: <command that runs the real job and waits for it>
- **Run base code**: <second worktree, or one-file swap command>
- **Read local state**: <one read query helper>
- **Sandbox host**: <host the scripts must see>
- **Allowlisted test accounts**: <ids or handles, owned by the user (never a teammate's); who approved, when>
- **Write log**: <path>
- **Deployed environments on the same sandbox**: <env, job, cron expression, file:line>

## Scripts

| File | What it does | Writes? |
|---|---|---|

## Scenarios

| Change | File | Result in one line |
|---|---|---|
```

## scenarios/<change>.md

```markdown
# <change>: <question in a few words> (<date>)

PR <link> head `<sha>`, base `<sha>`. Worktree stack `<name>`, vendor **sandbox**, local DB.

## Safety

Paths from this flow to a person (code on <ref>):
- <channel>: `<file:line>` → ... → `<vendor client method>`

Neutralized by: <capture runner / dead host / stopped worker ...>, in <which processes>. Stub self-test: <unlisted method threw>.

## Setup

- Local prep: <migrations, records marked processed, seeds>
- Temporary changes: <file, what>; reverted, `git status` clean.
- Sandbox data: existing <ids> read; created <ids> (write log entries <dates>).
- Order: <PR first, base second / any>, because <reason>.

## Results

| # | Case | Expected (code) | Base | PR |
|---|---|---|---|---|
| 1 | <case> | <outcome> (`file:line`) | <observed> | <observed> |

Allowed cell values besides an observed result: `not run`, `not seen: consumed by the <x> run`,
`unit-tested only (<spec>)`, `observed live on <env>, not run locally`.

Noise baseline: <second run of the same version: unchanged / what changed>.

## Observations (not regressions)

## Side effects

<sandbox writes (link the write log), deployed-environment duplicates with times>

## Not covered

<case, why (cadence, real delivery, concurrency, prod), and where it is covered instead>
```

## Write-log entry

```markdown
### <date> <time UTC>: <change>

- Script: `<script> <mode> <args>`; host printed: <sandbox host>
- Account: <allowlisted test account>
- Created/changed: <ids, statuses>
- Can be deleted: <yes / no (vendor)>
- Expected later effects: <e.g. deployed env will process it on its next sweep>
```

## PR verification comment (draft)

```markdown
**Sandbox verification** (base `<sha>` vs PR `<sha>`, same sandbox data, local stack)

| Case | Base | PR |
|---|---|---|
| <case> | <observed> | <observed> |

- Safety: no email, SMS or vendor-sent message possible (<how>).
- Not covered: <list>; unit-tested only: <list>.
- Mutation check: reverting <line> makes <test> fail.
- Readers of `<table>`: <each reader and the effect>.
```
