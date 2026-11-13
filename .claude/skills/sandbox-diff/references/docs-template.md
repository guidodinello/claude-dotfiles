# Per-project docs folder template

Use this only to bootstrap a missing folder. When the folder already exists in another shape, keep it: map each profile field below to where the folder keeps it (a workflow section, a section of a shared accounts file used as the write log), and note missing fields in the scenario instead of restructuring.

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

- **Base ref**: <target branch>; runs always use SHAs (open PR: merge-base; merged PR: first parent of the merge)
- **Worktree stack**: <how a PR worktree comes up; services to start; services never to start (scheduler)>
- **Usable-stack checks**: <tables exist, API answers, no scheduler container>
- **Migrate**: <command>
- **Seed a test account locally**: <command>
- **Run PR code**: <command that runs the real job and waits for it>
- **Run base code**: <second worktree, or one-file swap command; must take a base SHA, never a branch>
- **Decision-only runner**: <command that blocks every vendor write and records attempts>
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

PR <link> (open / merged): PR `<full sha>`, base `<full sha>` (<how derived>). Worktree stack `<name>`, vendor **sandbox**, local DB.
Mode: decision-only (writes blocked) / real writes. Earlier scenarios for this PR: <links, and whether their base SHA matches>.

## Safety

Paths from this flow to a person (code on <ref>):
- <channel>: `<file:line>` → ... → `<vendor client method>`

Neutralized by: <capture runner / dead host / stopped worker ...>, in <which processes>. Stub self-test: <unlisted method threw>.

## Setup

- Local prep: <migrations, records marked processed, seeds>
- Temporary changes: <file, what>; reverted, `git status` clean.
- Sandbox data: existing <ids> read; created <ids> (write log entries <dates>).
- Order: <PR first, base second / any>, because <reason>.
- Write-log check: latest entries for the account read; in-progress checks depending on it: <none / which>.
- Local DB: rows changed <tables>; restored / left changed (<how>).
- Base swap (if one-file): PR's other changed files <list>; base file imports none of them / additive only.

## Results

| # | Case | Expected (code) | Base | PR |
|---|---|---|---|---|
| 1 | <case> | <outcome> (`file:line`) | <observed> | <observed> |

Allowed cell values besides an observed result: `attempted, blocked: <call> <id>`, `not run`, `not seen: consumed by the <x> run`,
`unit-tested only (<spec>)`, `observed live on <env>, not run locally`.

Noise baseline: <second run of the same version: unchanged / what changed>.

## Observations (not regressions)

## Side effects

<sandbox writes (link the write log), deployed-environment duplicates with times; or `none, writes blocked`>

## Mutation check

| Changed line | Mutated | Tests failed as expected |
|---|---|---|

## PR comment draft

<the draft below, for approval; for a merged PR, note whether it should be posted at all>

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

## PR verification comment (draft, kept at the end of the scenario)

```markdown
**Sandbox verification** (base `<sha>` vs PR `<sha>`, same sandbox data, local stack, <decision-only: no vendor writes / real writes on a test account>)

| Case | Base | PR |
|---|---|---|
| <case> | <observed> | <observed> |

- Safety: no email, SMS or vendor-sent message possible (<how>).
- Not covered: <list>; unit-tested only: <list>.
- Mutation check: reverting <line> makes <test> fail; not mutation-checked: <lines>.
- Readers of `<table>`: <each reader and the effect>.
```
