---
name: model-frontier
description: "Trigger: a new model dropped, which model or effort should X use, re-evaluate our model setup, is this model change worth it, model retro, check a past model decision. Fetch the Artificial Analysis Intelligence Index for every effort level, plot intelligence against cost, propose moves per role, and measure past changes on our own transcripts."
---

# Model frontier

Picks the model and effort level for each role in our setup (orchestrator, worker
planning, worker coding, code review, review scoring) from the Artificial Analysis
Intelligence Index (AAII), then checks later whether the change cost what the index
predicted.

The roles, what each one runs today, and the file that sets it are in
`references/roles.json`. Past decisions, with their predictions and baselines, are in
`references/decisions.json`. `<skill-dir>` below is this skill's installed folder
(`~/.claude/skills/model-frontier`); the scripts find their data from their own path, so
they run from any directory.

## When a model drops, or to re-check the setup

1. **Fetch.** Add the new release's AA slug to `watch` in `references/roles.json` (the URL
   path of `artificialanalysis.ai/models/<slug>`), then run:
   `python3 <skill-dir>/scripts/aa_frontier.py fetch`
   This writes `~/.claude/model-frontier/snapshots/<date>-v<index version>.json`. The
   script reads the data embedded in the page with plain HTTP, no browser. If it fails
   with `scrape failed`, the page layout changed: fix the parser, don't guess numbers.
2. **Report.** Run `python3 <skill-dir>/scripts/aa_frontier.py report --previous <older snapshot>`.
   You get a table of every variant, the move options per role, and an SVG plot next to
   the snapshot. Open it with `open <path>.svg` and give the user the path. Diffs only
   work within one index version; the script refuses to compare v4 with v5.
3. **Judge each move.** Recommend; don't apply. Weigh:
   - **Frontier first.** A dominated move (a cheaper option scores at least as high) is
     never the answer. The report hides those.
   - **Points per extra dollar**, against how much the role matters. Planning and review
     catch errors early, so they justify more than routine coding.
   - **AA cost per task vs our cost.** Our sessions are mostly cache reads and cache writes.
     The "input price per token" column is the better guide for long agentic sessions.
     The retro check shows which one held, so read past `checks` in `decisions.json`.
   - **Price tiers AA doesn't show.** The claude-api skill's model table lists Haiku 5.5 at
     $0.50/$2.50 per 1M tokens above a 100K-token prompt (5x its base). Long Claude Code
     sessions pass that.
   - **How effort is set.** Effort is per session: subagents inherit it unless the Agent
     call sets `effort`; one on another model keeps its own default. `opusplan` runs both
     phases at one effort (verified; `evidence` in the worker-split decision), which is why orca workers are a planner session plus a coder
     session. Confirm a change by reading the per-turn `(model, effort)` in a transcript.
   - **What the index measures.** AAII is a general benchmark, not our codebase. Use it to
     rank options, and the retro to confirm.
4. **Record, then apply.** Before changing any flag, record the decision with its baseline.
   Transcripts expire after `cleanupPeriodDays` (30 by default), so the baseline is gone if
   you wait:
   `python3 <skill-dir>/scripts/model_retro.py record --id <yyyy-mm-dd-short-name> --kind code-review --from claude-sonnet-5-5@medium --to claude-sonnet-5-5@high --change "<what changed, in which file>"`
   Add one `--verify "<what to confirm at runtime>"` per thing a diff can't prove, such as
   "the first review shows claude-sonnet-5-5@high". `check` lists open items until
   `model_retro.py verified --id <id> --item <n>` marks them done.
   Then make the change in the file named by `set_in`, update `roles.json`, and commit
   both with `decisions.json`.

## Checking a past decision

Run `python3 <skill-dir>/scripts/model_retro.py check --id <id>`, and add `--save` to store the result
in the decision. It measures sessions of the decision's kind that ran the new variant (the
change goes live at merge and sync, not on the decision date) and compares:

- **Cost:** median API-equivalent dollars per session before and after, against the AA
  cost ratio the decision predicted.
- **Quality proxies:** findings per review from the transcripts. Acceptance rates come from
  `babysit-prs/scripts/reviewer_leaderboard.py`, which gives each reviewer model, effort and
  scorer configuration in the review footer its own row. Reviews posted before the footer
  carried effort and scorer show the bare model.

Wait for at least 10 sessions after the change, or the comparison is noise. Report it as
"index went from X to Y; sessions now cost Z times as much (AA predicted W)", and say
whether the quality proxies moved.

`model_retro.py measure --kind <kind>` prints the current profile of one session kind
without recording anything.

## Gotchas

- The variant URLs (`/models/<release>-medium`) redirect to the max variant. Only the release
  page holds every effort level, which is why `fetch` reads release pages.
- Blogs that quote AA often copy older index versions. Use only a snapshot.
- Each message is logged once per content block with the same usage, so `model_retro.py`
  dedupes by message id. Summing raw lines overcounts cost.
- Session kinds match on the first prompt only. Matching anywhere would count a long session
  that ran one review as a review.
- Snapshots and measurements stay local. Only `roles.json` and `decisions.json` are
  committed, and they hold numbers, not session ids, paths or repo names. This repo is public.
