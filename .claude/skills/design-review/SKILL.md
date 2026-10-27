---
name: design-review
allowed-tools: Bash Read Grep Glob Agent
description: >
  High-level design review of a pull request, branch, or diff. Reports the
  properties of the change rather than line-level defects - the design
  decisions and the alternatives they rejected, the quality attributes each
  decision serves, the trade-offs it costs, the invariants and what guards
  them, and the risks and open questions - so the team can discuss the
  architecture before or instead of line-by-line review. Use when asked for a
  "design review", to "review the architecture of this PR", "what are the
  properties of this PR", to "discuss design decisions", or to write an
  ADR-style summary of a change. Complements code-review and pr-conventions;
  does not replace them. Read-only - never edits code or posts to GitHub
  unless asked.
---

## Goal

Make the design of a change discussable. A line-level review asks "is this
code correct?"; this skill asks "are these the right decisions, and do we
know what they cost?". The output is a short, ADR-shaped report the team can
argue about in a PR thread or a meeting.

A well-designed PR yields few findings. Most of the report is description
(decisions, attributes, guards), not criticism. Never manufacture concerns to
fill the template: an empty Risks section is a valid result.

Sibling skills, and where the line sits:

| Skill | Question it answers |
|-------|---------------------|
| `code-review`, `pr-conventions` | Line-level bugs, project standards, naming, reuse |
| `improve-codebase-architecture` | Where the *existing* codebase should be deepened |
| `design-review` (this) | What *this change* decided, why, and what holds it in place |

## References

| File | Contents | Read it in |
|------|----------|------------|
| [`references/principles.md`](references/principles.md) | Frameworks (ISO/IEC 25010 vocabulary, quality attribute scenarios, ADR/MADR, fitness functions) and the curated principle catalog P1-P21, each with smell, review question and source | Steps 3-5 |
| [`references/example.md`](references/example.md) | A complete worked report in the exact output format, on an unrelated synthetic change - a format reference, not an answer key | Step 6 |

---

## Invocation

Accepts one of:

- **A PR number or URL** - fetch with `gh`:

  ```bash
  gh pr view <pr> --json number,title,body,baseRefName,headRefName,files,url
  gh pr diff <pr>
  gh pr view <pr> --comments   # design discussion often lives here
  ```

  Diff against the PR's own `baseRefName`, never an assumed `main`. A
  stacked PR's base is the PR below it, and that diff is the change under
  review.
- **A branch** - find its real base, then diff from the merge base:

  ```bash
  git rev-parse --abbrev-ref <branch>@{upstream}       # tracking info, if set
  gh pr list --head <branch> --json number,baseRefName # an open PR names the base
  gh repo view --json defaultBranchRef -q .defaultBranchRef.name \
    || git symbolic-ref --short refs/remotes/origin/HEAD   # prints origin/<name>
  git diff "$(git merge-base origin/<base> <branch>)"...<branch>
  ```

  Use the open PR's base when there is one (stacked branches); otherwise the
  repository's default branch. State the base you used under Coverage.
- **A diff or patch file** - read it directly.
- **Nothing** - review the current branch the same way; if the current branch
  *is* the default branch, ask which change to review.

This skill is read-only. Do not edit files, push, comment on, or approve the
PR. If the user asks for the report to be posted, post it as one PR comment.

---

## Step 1 - Gather context

1. Read the PR title, description, and comments. Follow links to tickets,
   design docs, and ADRs (`docs/adr/`, `docs/decisions/`, `adr/`) that the PR
   cites or that cover the touched modules. If a ticket link cannot be
   followed, use a tracker CLI or MCP only when one is already configured;
   otherwise note it under Coverage and work from the PR text and code. Never
   guess what a ticket says.
2. Read the diff. For each touched module, read enough of the surrounding,
   unchanged code to know what the change plugs into.
3. Note which tests, schema migrations, CI config, and lint rules the PR adds
   or changes - these are where guards live (Step 4). Then check **where each
   guard runs**:
   - CI workflows (`.github/workflows/`, other CI config): which jobs run
     which tests, on which events.
   - Git hooks (`.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`): a hook
     is local and skippable (`--no-verify`, a missing install), so a test that
     runs *only* there is not an automatic guard.
   - Boot or init checks: which processes or apps actually execute them (API,
     worker, CLI, scheduled job). A check in one of several entry points
     guards only that one.

For a large diff (roughly 30+ files or several subsystems), spawn one Explore
agent per subsystem to return "what changed structurally, and which new types,
boundaries, or extension points it introduces". Do the decision analysis
yourself from their summaries.

## Step 2 - Identify the decisions

A decision is a choice another competent engineer could reasonably have made
differently. Look for:

- a new abstraction, module, base class, decorator, or extension point;
- where a rule is enforced (one choke point vs. scattered checks);
- where state or configuration lives, and who is its source of truth;
- a data representation (types, schema, enum vs. string, nullability);
- a new dependency, protocol, or boundary between components;
- what is enforced by the machine (type, constraint, test) vs. by convention.

For each decision record the **alternatives it rejected**. Mark each one
**explicit** (stated in the PR, a comment, or an ADR) or **implied** (the
obvious other way the code could have gone). Keep the list to the decisions
that shape the change - typically 1 to 4, up to about 5 when the PR genuinely
makes that many (a data-migration strategy often is one). Fewer is better:
mechanical consequences of a decision are not separate decisions.

## Step 3 - Map decisions to quality attributes

Name each attribute with the ISO/IEC 25010:2023 vocabulary
(`principles.md` §1.1) and tie it to concrete code: a file and symbol, not a
claim. "Improves security" is not an entry; "every write goes through
`OrderRepository.save()`, so no path skips the audit log" is. When an attribute claim is
vague, restate it as a quality attribute scenario (§1.2) to see whether the
code actually delivers the response.

## Step 4 - Find invariants and their guards

List what must always hold for the design to be correct. For each invariant,
name the guard and its kind:

| Guard kind | Example |
|------------|---------|
| Type (compile time) | the illegal state cannot be constructed |
| Test | a unit, snapshot, or drift test fails when it breaks |
| DB constraint | `NOT NULL`, `CHECK`, unique index, FK |
| Runtime assertion | a check that throws or fails closed in production |
| Boot-time check | validation that refuses to start |
| Convention only | a comment, a doc, a reviewer's memory |

Treat guards as fitness functions (§1.4) and fill the `Fitness function?`
column with one of:

- **Yes** - runs automatically on every change or every run and fails loudly.
- **Partly** - automatic but escapable: runs only in a skippable local hook,
  only in one of several processes that need it, or only on some CI events.
  Say which in the cell.
- **No** - convention only, or nothing fails when the invariant breaks.

Every `Partly` and `No` invariant the design depends on is a finding, and it
lives **only** in section 4's **Unguarded** list (as U1, U2, ... with the
principle and the cheapest guard that would close it). Section 5 refers to
it by ID and does not repeat it. Prefer the strongest cheap guard: a type
beats a test, a test beats a comment.

## Step 5 - Check against the principle catalog

Walk `principles.md` §2 for the attributes Step 3 surfaced. Raise a finding
only when you can point at code that shows the smell. Every principle-based
finding names the principle, its catalog ID, and its source: the link, or for
a house rule the words "house rule" and the file path (`principles.md` §2
marks which entries are house rules). Also record the principle a decision
applies in the `Principle` column of section 2 - that is part of the design
record, not praise. Write `-` when no catalog principle applies; never force
one.

## Step 6 - Write the report

Use the template below exactly; `references/example.md` shows a filled one.
Keep it short: the reader should finish in under five minutes.

```markdown
## Design review - <PR title> (<#number or branch>)

**Summary.** <Two or three sentences: what the change does structurally.>

### 1. Decisions

#### D1 - <short noun phrase>

- **Chose:** <what the code does>
- **Rejected:** <alternative> - <why not> (explicit | implied)
- **Why:** <the force that decided it>

### 2. Quality attributes

| Decision | Attribute (ISO/IEC 25010) | Where the code delivers it | Principle (P<n> or -) |
|----------|---------------------------|----------------------------|-----------------------|

### 3. Trade-offs

| Decision | Cost | Accepted because |
|----------|------|------------------|

### 4. Invariants and their guards

| Invariant | Guard | Kind | Fitness function? (Yes / Partly - why / No) |
|-----------|-------|------|---------------------------------------------|

**Unguarded:** <"None.", or one bullet per Partly/No invariant:>

- **U1 - <title>.** <What breaks and how.> Principle: <name> (P<n>, <source>).
  Cheapest guard: <what would close it>.

### 5. Risks and open questions

- **R1 - <title>.** <Evidence: file/symbol.> Principle: <name> (P<n>,
  [source](url) | house rule `<path>`). Question for the team: <what to decide>.
- **Q1 - <title>.** <An open question that is not a defect.>
- Unguarded invariants: see section 4 (U1, ...).   <omit if none>

### 6. Rollout and data migration   <optional: omit when not applicable>

- **Deploy order:** <migration vs. app vs. workers; what breaks if reversed>
- **Data:** <migrations on populated tables, backfills, locks, duration>
- **Exposure window:** <what is unprotected or inconsistent between deploy
  and first run, or until a flag flips>

<Coverage: the base the diff was taken against, what was read (diff, PR body,
linked docs, N surrounding files), and what was not - including links that
could not be opened.>
```

---

## Calibration rules

- **Describe first, judge second.** Sections 1-4 and 6 describe the design;
  findings live only in section 4's Unguarded list and section 5, and each
  finding appears in exactly one of them. A rollout concern found in section
  6 becomes an R item in section 5.
- **No manufactured findings.** If the design is sound, say so in one line
  under section 5. Do not pad with generic advice ("consider adding more
  tests").
- **Every finding has evidence and a source.** A file and symbol from the
  diff, plus a named principle with its link (or "house rule" and its path).
  A concern you cannot tie to a
  catalog principle is phrased as a question, not a finding.
- **Rejected alternatives must be plausible.** List what a competent engineer
  might actually have done, not straw men.
- **Name costs honestly.** Every decision costs something. A trade-offs table
  with no cost in it means the analysis stopped early.
- **Stay at design altitude.** Line-level bugs, naming, and style belong to
  `code-review` / `pr-conventions`. Mention one only if it breaks an
  invariant from section 4.
- **The principles conflict.** Locality of behaviour pulls against DRY
  (P15 vs. P14), and `principles.md` §2 lists the other common tensions
  (for example a complete guard test is a second representation of what it
  guards, P10 vs. P14). When a decision picks a side, record it in section 3
  as "Tension P<a> vs P<b>", not as a violation.
