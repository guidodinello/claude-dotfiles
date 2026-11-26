---
name: metacognition
description: 'Trigger: design how to tackle this, think before building, how should we approach X, a big or complex task, a task spanning several components, an unfamiliar area, plan the approach first. Produces a brief (what to build, what we need to know, how to build it, how to verify it) and stops for approval before any implementation. Not for small or well-understood changes.'
---

# Metacognition

Think about how the work should be done before doing it. The output is a
short brief the user approves. No implementation happens in this skill.

## Why this exists

On a big task the expensive mistakes are made in the first ten minutes:
building the wrong thing, building on a guess about how the code behaves, or
finishing with no way to tell whether it works. All three are cheap to catch
before the first edit and costly after. Starting to code feels like progress,
so the questions below get skipped unless something forces them.

A brief written from memory is worthless. "Add tests, verify it works" fits
any task and changes nothing. Every line of the brief must be specific to this
task and this codebase, which means reading before writing.

The reasoning and sources behind each step are in
`references/metacognition-philosophy.md` (heuristics M1 to M27, each with its
evidence strength). Read the section for a step when a judgment call comes up
in it, and cite the heuristic ID when it decides something. Do not read the
whole file up front.

## Scope: decide how much design this task needs (M1 to M4)

Design effort should scale with novelty, with what is hard to reverse and with
how much breaks if the work is wrong. More deliberation is not always better:
it has a measured cost, and a written brief is not evidence that the work will
be good. The checks and the user's approval carry that weight.

- If the change is obvious, local and easy to undo, say so in one line and
  skip the brief.
- Otherwise keep the brief to what would change a decision. If a section has
  nothing task-specific to say, leave it out.

## Method

Work through the four questions in order, then loop: the answer to question 4
often changes the answer to question 3.

### 1. How do we know what to build? (M5 to M8)

- Find the source of the requirement: the ticket, the user's message, a
  design, a failing behaviour. Quote it. If there are several sources, check
  that they agree. Check that the source is still current: a ticket can be
  partly done already.
- If the request can be read in more than one way and the readings lead to
  different work, say which reading you chose, which you rejected and what in
  the request or the project made you choose. Picking one silently hides the
  most expensive mistake available.
- State the goal as an observable outcome ("a clinician can export the list as
  CSV"), not an activity ("add an export service").
- State what is out of scope: things that could reasonably be goals and are
  not.
- Do not trust your own sense that the task is well specified. Split what is
  unclear into "the code can answer it" and "only the user knows". The second
  group becomes the open questions.

#### What an expert would ask

The user may not be an expert in the area the task touches, and then cannot
ask for properties they do not know exist. Do not limit the brief to what was
asked for.

- Name the domains the task touches (for example file handling, auth, data
  migration, payments, accessibility).
- For each, list the properties a practitioner in that domain would insist on
  and the questions they would ask first. For a script that moves files that
  is reversibility, no overwrites, a dry run and what happens to duplicates.
- Ground the list. Use the repo's curated skills and rules where one covers
  the domain (`/write-tests`, `/security-audit`, `/hipaa-audit`,
  `/db-scalability-audit`, `/accessibility-review`, `.claude/rules/`), then
  official docs or a quick search. A property recalled from memory with no
  source is marked as such.
- Keep only the properties that matter for this task. For each one give a
  one-line plain-language reason and a recommended default, so the user can
  choose without already knowing the field.

### 2. What do we need to know to assess how it should be built? (M9 to M14)

List the unknowns that would change the approach. For each one, say how it
gets resolved:

- **Read**: the answer is in the code, the docs or the data. Resolve these now,
  before writing the brief. For "how does this flow actually work", use
  `/backward-trace`.
- **Run**: the answer needs an experiment (a spike, a query, a timing). Run it
  now if it is cheap and read-only. Otherwise make it the first slice.
- **Ask**: only the user or a third party knows. List it as an open question.

A feeling of understanding how a mechanism works is weak evidence, so read the
code that implements it.

Follow the change downstream before choosing an approach. Find what reads,
copies, builds, syncs or deploys the files you will touch (grep for their
names and for their directory in scripts, CI and config) and read it. An
approach that is correct inside the files can still fail at the step that
ships them.

Before writing the brief, go through your assumptions one by one. If a grep or
a file read can settle one, do it now: "I have not read it" is not an
assumption, it is a skipped step. Only what could not be checked goes in the
brief, with what breaks if it is wrong.

### 3. How do we build it? (M15 to M17)

- Describe the approach in terms of the components it touches, named exactly.
- Name the alternative you rejected and the reason. If you cannot name one,
  you have not looked at the option space.
- Cut the work into slices that each end in something checkable. Put the
  riskiest or least understood slice first, so a wrong assumption surfaces
  while changing course is still cheap.
- Say what is hard to reverse (a migration, a published interface, deleted
  data) and how that step is guarded.
- Say how the work will be run when that is a real choice: which existing
  skills apply, what is delegated to a subagent, whether it needs a worktree.

### 4. How do we verify it was built correctly? (M18 to M24)

- Give each slice a done-signal: the command, test or screen state, and the
  result that counts as a pass. Choose it now. A check chosen after the code
  exists tends to be one the code already passes.
- Say what makes the check fail. A check that cannot go red proves nothing.
- Pick the level that crosses the real boundary where the risk is. A unit test
  with the boundary mocked does not show that the integration works.
- Prefer an external signal (a test run, a compiler, the real system, the
  user) over rereading your own work. Self-review is not verification.
- If the check needs something that does not exist yet (a fixture, a harness,
  a seeded sandbox), that is work. Add it to the slices.
- Say what the checks cannot see, so the user knows what is still taken on
  trust.

## The brief

Reply with this structure. Keep it to about one screen: include a fact only if
it changed the approach, and cite it as `path/file.ext:line` with the real
line number.

```markdown
## Work design: <task>

**Goal:** <observable outcome>. Source: <ticket / message / design>.
**Reading:** <only if the request was ambiguous: the reading chosen, the one
rejected, and why>
**Out of scope:** <what this does not cover>

**Properties to aim for** (not asked for, but an expert would require them)
- <property>: <why it matters, in plain words>. Default: <recommendation>.
  Source: <skill / doc / "from memory">

**What we know** (checked)
- <fact that shaped the approach> (`path/file.ext:line`)

**Assumptions** (could not be checked)
- <assumption>, and what breaks if it is wrong

**Approach:** <components touched and how>
**Rejected:** <alternative>, because <reason>
**Hard to reverse:** <step and its guard, or "nothing">

**Slices**
1. <slice>. Done when: <command or check> shows <result>. Fails when: <what
   makes it go red>
2. ...

**Not covered by the checks:** <what is still taken on trust>

**Open questions**
- <question only the user can answer>
```

Then stop and wait for the user. Do not start the first slice in the same
turn: the point of the brief is that it can still be changed.

## After approval

Build slice by slice, running each done-signal before moving on. If a slice
shows the brief was wrong, say so and revise the brief before continuing,
rather than quietly working around it.
