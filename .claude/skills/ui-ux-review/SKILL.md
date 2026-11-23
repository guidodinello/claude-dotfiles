---
name: ui-ux-review
allowed-tools: Bash Read Grep Glob Agent
description: 'Evaluate UI/UX from a screenshot, recording or component: flow, consistency, layout, copy; findings only.'
---

## Goal

Catch UX defects that linters and typecheckers can't: dead-end flows, missing
loading/empty/error states, inconsistent design tokens, unreadable copy, and
interaction patterns that violate established human-factors heuristics
(`references/heuristics.md`). A well-calibrated run on a healthy screen produces few or no blocker/high
findings — don't manufacture severity to fill out a report.

This skill is frontend-agnostic. Most heuristics apply to any UI (web or mobile);
a few (thumb zones, bottom sheets, safe-area insets, gesture conventions) are
mobile-specific and should be skipped when reviewing a web frontend.

## Invocation

Accepts one of:

- **A screenshot or screen recording path** — read it directly (Read supports
  images; for a recording, ask the user for representative frame(s) or extract
  them with `ffmpeg -i <recording> -vf fps=1 frame_%03d.png` into the scratchpad
  directory).
- **A component/screen file path or directory** — read the source directly. If
  the `run` skill is available and the app is easy to launch, prefer driving the
  real screen and screenshotting it over reading JSX alone — static analysis
  misses runtime-only defects (missing loading state on a real fetch, layout
  overflow with real data).
- **Nothing specific** — ask the user which screen(s) or flow to review.

---

## Step 1 — Scope the review

Identify:

- Which screen(s)/component(s) are in scope, and whether this is web or mobile
  (skip mobile-only heuristics for web).
- Whether this is a **quick check** (single component, e.g. during feature
  review) or a **full audit** (periodic sweep across a flow or the whole app).

For a full audit across many screens, spawn parallel Explore or general-purpose
agents — one per screen/flow — each given the relevant heuristics from `references/heuristics.md`
and asked to return findings in the Report Format below. For a quick check on one
component, review it directly without spawning agents.

## Step 2 — Apply heuristics in priority order

Read `references/heuristics.md` (if missing, read
`$HOME/.claude/skills/ui-ux-review/references/heuristics.md`) and work through it
using its **Quick audit ordering checklist** (at the end) rather than UH1→UH35 in sequence — it front-loads the highest-signal,
cheapest-to-verify checks first (state coverage, tap targets, safe areas,
keyboard handling, button/error copy) so a time-boxed review still catches the
defects that matter most.

For each heuristic, only flag what you can point to concretely — a specific
file:line, screenshot region, or missing state branch. Skip heuristics whose
"signal strength" is Weak/Medium unless you have the context (domain knowledge,
full flow visibility) that heuristic's "what to look for" section calls for.

## Step 3 — Rate severity

Map findings to severity, not just heuristic priority — a UH1 (state visibility)
violation on a rarely-used settings row is a `low`, while the same violation on
the primary checkout button is a `blocker`:

- **blocker** — breaks the task (dead end, crash-equivalent, data loss risk,
  inaccessible primary action)
- **high** — works but actively misleads or frustrates users on a common path
- **medium** — noticeable friction or inconsistency, not on the critical path
- **low** — polish issue, minor inconsistency
- **nit** — cosmetic, purely stylistic

## Step 4 — Report

Do not silently drop low-signal items — list them under `nit`/`low` rather than
omitting them, but keep the top of the report focused on `blocker`/`high` so it's
actionable at a glance.

### Report format

```
## UI/UX Review — <screen/flow name>

### Blocker
- [UH#] <file:line or screenshot region> — <what's wrong> → <fix>

### High
- ...

### Medium
- ...

### Low / Nit
- ...

<N> findings across <M> heuristics checked. Skipped: <heuristics not applicable
and why, e.g. "mobile-only, this is a web screen">.
```

If no findings survive Step 3, report `No UX issues found` plus a one-line note
on what was checked (don't leave the reviewer guessing what was covered).
