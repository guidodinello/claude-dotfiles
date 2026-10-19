---
name: dev-docs-index
description: "Conventions for organizing and navigating a repo's my-dev-things/ folder (a personal non-code knowledge base — docs/, data/, scripts/, etc. — kept alongside a project's code across several client engagements). Use when creating a new subfolder or file under any my-dev-things/, deciding where a new investigation/bug/idea/query doc should live, writing or updating a README.md index there, or when asked to find prior context on a topic inside a my-dev-things/ tree. Also owns the my-dev-things/work-guide/ layout and the post-meeting routine (run it when the user pastes a meeting transcript). The core rule: every folder and subfolder needs a README.md index, so the tree stays discoverable without needing to be preloaded into context."
---

# my-dev-things/ documentation conventions

## Why this exists

Several projects (e.g. `project-a/my-dev-things/`, `project-b/my-dev-things/`,
`project-c/my-dev-things/`) keep an accumulated knowledge base alongside their code:
investigations, bug write-ups, incident reports, feature docs, ready-to-run queries,
ideas, tool output. It is **not code** — nothing here is loaded automatically, and
nothing here should be. It is also **local**: `my-dev-things/` is gitignored in every repo
and never committed or shared, so never stage or commit anything under it. The failure mode this skill prevents is a doc that exists but is
*unreachable*: written once, never linked from anywhere, and effectively lost the next
time someone (human or Claude) needs the context it holds.

The fix is a plain tree convention, not a database: **every folder and every subfolder
under a `my-dev-things/` has a `README.md`** that says, in a few lines, what the folder
is for and what's in it — and if it has subfolders, links to each of *their* `README.md`
files. Discovery becomes a walk down READMEs, one level at a time, reading only the
branches relevant to the current task. This keeps a session's context lean (you read one
short index, not fifty files) while keeping everything reachable (that index tells you
exactly where to go next).

This applies inside whichever repo you're currently working in. Each repo's
`my-dev-things/` tree is independent — there's no cross-repo index, and there doesn't
need to be.

## The rule

1. **Every folder under a repo's `my-dev-things/` needs a `README.md`.** This includes
   `docs/` itself, every topic folder inside it, and every subfolder of those,
   recursively — for as many levels as the folder tree goes.
2. **A folder's `README.md` briefly states its purpose and contents**, then — if it has
   subfolders — links to each subfolder's own `README.md` rather than re-describing what's
   inside them. Don't duplicate a child's content in the parent; point to it.
3. **A leaf folder's `README.md` (no subfolders) lists its files** with a one-line
   description of each, so a reader can pick the right file without opening several.
4. **If the repo has a master discovery table elsewhere** (e.g. a docs-subdirectory table
   in a project-level `CLAUDE.md` or similar onboarding doc), register new top-level
   `docs/` subfolders there too, and keep it in sync — a folder with a good README but no
   row in that table is still hard to find on a cold start, and a row pointing at a
   stale/missing README is a broken promise. If the repo has no such master table, the
   top-level `docs/README.md` (or equivalent) is the entry point instead — make sure it
   lists every direct child.
5. **Skip README.md only for**: non-navigational leaf files that are clearly
   self-contained data (e.g. an example JSON/CSV fixture sitting alone, no subfolder),
   and top-level utility folders (`scripts/`, `templates/`, `claude-artifacts/`) which
   are code/config, not the knowledge-base tree this convention targets.

## What goes in a README.md here

Keep it short — a few sentences to a dozen lines for most folders. Don't write a report
in the README; write a *map* to the reports.

**Leaf folder** (files, no subfolders) — see `project-a/my-dev-things/docs/feature-status/README.md`
for a fully worked real example:

```markdown
# <Folder purpose, one line>

<One paragraph: what question this folder answers or what work it covers, and current
status/date if the content has a shelf life.>

## Documents

| File | What it covers |
|---|---|
| `foo.md` | One line |
| `bar.md` | One line |
```

**Parent folder with subfolders** — see `project-a/my-dev-things/docs/investigations/README.md`
or, for a multi-track work area with active/historical status per track,
`project-a/my-dev-things/docs/migration/phase-2/README.md` (the gold-standard
example: a routing table for "if you want to work on X, start at Y," plus a status table
kept current instead of a chronological log):

```markdown
# <Folder purpose>

Index of <what>.

- **subfolder-a/** — <one line, what it's for>. Start at its
  [README](./subfolder-a/README.md).
- **subfolder-b/** — <one line>. Start at its [README](./subfolder-b/README.md).
```

If a parent folder mixes loose files and subfolders (like project-a's
`docs/feature-status/`, which has both top-level `.md` files and a `spike/`
subfolder), give the loose files a Documents table and the subfolders their own
bullet/link — don't force one format over the other.

## Cite the source for every finding

A finding without a source is a claim someone has to re-derive from scratch the next time it
matters. Every fact, discovery, or claim written into a doc under `my-dev-things/` carries its
source right where it's stated:

- **External source** (a vendor doc, a GitHub repo, a forum thread, a pricing page): a
  markdown link to the exact URL, plus the date it was read if the content is the kind that
  changes (pricing, docs, a live console).
- **Internal source** (another file in this repo, a decision doc, a Slack thread, code): a
  repo-relative path, or a channel/timestamp reference precise enough to reopen it.
- **Direct observation with no URL** (a screenshot, something seen live in a console, a
  command you ran yourself): say so explicitly — *"direct observation, screenshot taken
  18 Sept"* — rather than leaving the claim unsourced. The observation itself is the record.

Put the citation inline, next to the claim, not only in an end-of-document source list — a
reader skimming one paragraph should not have to cross-reference a table to know where it
came from. A **Sources** table at the end of a doc (claim → link) is a good *index* for
re-finding things later, once a doc has enough citations to want one, but it supplements the
inline citation, it doesn't replace it.

When a doc revises or corrects an earlier claim, cite the new source the same way, and say
what it superseded — the docs already in this tree do this well (e.g. "Corrected 7 Sept,
against Zoom's own words: ..."); keep doing it.

If you're editing an older doc in this tree and touch a claim that has no source, add one if
you still know it. Don't let the gap widen, but don't block unrelated edits on backfilling
every old citation either.

## The work-guide/ folder and the post-meeting routine

Some repos keep a `my-dev-things/work-guide/` folder: how the user works on that project
(visibility, pre-presentation checklist, working agreements, weekly cycle) plus a record of
every meeting. This section owns the parts that are the same in every repo. Each repo's
`guide.md` owns only its project specifics and links here for the rest.

### Layout

```
work-guide/
  README.md      index; links to the raw transcripts folder and meetings/README.md
  guide.md       project-specific working rules
  meetings/      one summary per meeting: YYYY-MM-DD-<meeting>.md
    README.md
raw/             as-downloaded transcripts, never edited (either my-dev-things/raw/
  README.md      or work-guide/raw/; the work-guide README says which)
```

### Post-meeting routine

Run it when the user pastes a meeting transcript or summary.

1. Save the transcript as-is, date first in the file name, into the raw folder the
   work-guide README links to. Never clean it up: corrections go in the summary.
2. Write `meetings/YYYY-MM-DD-<meeting>.md`: decisions, the user's pending items (owner
   and next step), what others owe the user. Cite the raw transcript at the top. Mark
   every point the transcription garbled as **(unclear)**.
3. Recall check: ask the user about each **(unclear)** point, one at a time, without
   showing the transcript snippet first. The user answers from memory, then update the
   summary with the answer. Show the snippet only if asked. The point is twofold: more
   accurate notes, and making the user recall the meeting. The notes are personal, so
   never suggest asking the other participants.
4. Move actionable items to the repo's tracker as `guide.md` names it. The meeting file
   is the record, not a tracker.

Before a meeting with someone, read the last file in `meetings/` with them.

### Routing from CLAUDE.local.md

A repo with a work-guide tells Claude when to read it, in its gitignored `CLAUDE.local.md`:

```markdown
## Work guide (read at these moments)

`my-dev-things/work-guide/guide.md` holds how the user works on this project. Read it,
without waiting to be asked, when:

- Building an artifact or analysis that will be presented to the team: apply its
  pre-presentation checklist.
- The user pastes a meeting transcript or summary: run the post-meeting routine (the
  `dev-docs-index` skill owns it; `guide.md` adds the project specifics).
- Planning the week or a demo: apply its visibility and weekly-cycle sections.

Before a meeting with someone, check `work-guide/meetings/` for their last one.
```

## Navigating as Claude — read only what the task needs

When looking for prior context on a topic inside a repo's `my-dev-things/`:

1. Start at that repo's master discovery table if it has one (see rule 4), otherwise at
   `docs/README.md`.
2. Open the relevant folder's `README.md`. If it points to subfolders and one clearly
   matches the task, descend into *that one* — don't open every sibling "just in case."
3. Stop descending once a README's file table names the specific doc you need, and read
   only that doc.

This mirrors how the docs were structured to be read — don't defeat the tree by grep-ing
across the whole `my-dev-things/` for a keyword before checking whether a README already
points straight there. Grep is the fallback for when the tree doesn't have an obvious
entry point, not the first move.

## When creating a new subfolder

1. Write the folder's own content first.
2. Add a `README.md` in it — even a 3-line one is better than none. If it has its own
   subfolders, make sure each of those has a README too before you consider the folder
   done.
3. Add a link to the new `README.md` from its **parent's** `README.md`.
4. If the new folder is a new top-level `docs/` subfolder and the repo has a master
   discovery table, add a row for it there too.
5. If the folder is investigation/incident/multi-doc work (not a single file), prefer the
   `migration/phase-2/`-style pattern once it grows past 2-3 docs: a `README.md`
   that's a routing table ("if you want X, start at Y") plus a status table you keep
   current, rather than letting the README become a chronological append-only log.

## Cross-reference: a personal pending-items index, if one exists

Some workspaces keep a personal, untracked, cross-repo pending-items index (active
incident follow-ups, open sweeps, in-flight threads) — e.g. a `PENDING.md` excluded via
`.git/info/exclude`. Like `my-dev-things/` it is local, but it sits outside any repo's
`my-dev-things/` tree.

If such an index exists in a workspace you're in:

- **Direction: it points into `my-dev-things/`, never the other way.** When you're
  working on something in a repo's `my-dev-things/` that's still active or that you'll
  resume later, add a line to that personal index pointing at the relevant folder's
  README. Don't add anything to a `my-dev-things/` README that assumes the personal
  index exists — it's per-contributor and may differ or not exist at all.
- It doesn't get a `README.md` under this convention itself — it isn't part of any
  repo's `my-dev-things/` tree; it's a personal scratch file that happens to reference
  into those trees.

## Checking for gaps in a repo you're working in

There's no permanent gap list here — it goes stale the moment someone adds a folder.
Instead, check on demand for whichever repo you're in:

```bash
find my-dev-things/docs -type d | while read -r d; do
  [ -f "$d/README.md" ] || echo "$d: NO README"
done
```

If you're already working inside a folder that's missing its README for another reason,
add it while you're there rather than leaving it for later — that's how the debt stays
small instead of accumulating.
