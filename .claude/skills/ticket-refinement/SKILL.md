---
name: ticket-refinement
description: >
  Use this skill whenever the user wants to write, refine, or break down a
  subtask for a software ticket — especially backend endpoints, frontend
  components, or API integrations. Trigger when the user shares a user story,
  acceptance criteria, or ticket scope and asks for a subtask, refinement card,
  or implementation breakdown. Also trigger when the user says things like
  "help me refine this", "write a subtask for X", "break this down", or
  "create a card for the endpoint / component / feature". This skill produces
  structured, audience-appropriate subtask write-ups for developers, PMs, and
  QAs alike.
---

# Ticket Refinement Skill

Produces a structured subtask write-up from a user story or ticket description.
Audience is mixed: developers, PMs, and QAs — so keep language clear and avoid
deep implementation jargon unless asked.

---

## Clarifying Questions (ask before writing)

If the following are not already clear from the conversation, ask them before
producing the subtask. Group them into one message — don't ask one at a time.

1. **What kind of subtask is this?** (e.g. backend endpoint, frontend component,
   data migration, integration, etc.)
2. **What data sources or services are involved?** (e.g. local DB, third-party
   API, internal service)
3. **What already exists** that this subtask can build on or integrate with?
4. **What is the association or relationship model** if any (e.g. how entities
   relate to each other)?

Skip questions that are already answered in the user story or acceptance
criteria.

---

## Output Template

Use this structure for every subtask. Omit a section only if it genuinely does
not apply (e.g. no edge cases for a trivial UI tweak).

Use `##` headings for each section (e.g. `### Context`, `### What Needs to Be Built`).

Always wrap the entire output in a markdown code block (` ```markdown ... ``` `) so the user can copy raw markdown directly.

Use backticks for:
- File paths and directory names (e.g. `src/components/Banner.tsx`)
- Route paths (e.g. `/quiz/step-1`)
- Field names, parameter names, and HTTP methods (e.g. `GET`, `user_id`)
- Component or function names when referenced inline (e.g. `WhereToStartBanner`)

Do NOT use backticks for plain English descriptions, section prose, or AC items.

---

## Context

1–3 sentences explaining _why_ this subtask exists, what problem it solves, and
where it fits in the bigger feature. Mention relevant existing models, services,
or data sources. Written so a PM or QA can understand it without technical
background.

---

## What Needs to Be Built

A clear list of the concrete deliverables. For each item:

- State _what_ it is (route, component, service method, etc.)
- State _what it does_ in plain language
- Focus on **what** is being built and **why**, not **how** it is implemented

Keep this section high-level — it should read like a feature spec, not a code
review. Do NOT include:
- Prop names, function signatures, or component internals
- CSS classes, styling tokens, or layout implementation details
- State management wiring, hook usage, or data-fetching patterns
- Any detail that describes the developer's chosen implementation approach

A good test: would this bullet still be valid if a developer chose a completely different implementation strategy? If yes, keep it. If no, cut it.

Use a numbered or bulleted list. Use backticks for specific technical references
(file paths, component names, route paths) but keep prose plain.

---

## Acceptance Criteria

A bulleted list of testable outcomes — written so a QA can use them directly to
write test cases. Each item should be a complete, verifiable statement.

Include both the happy path and edge cases inline. Pull edge cases from:

- Nullable or optional fields
- Empty / zero-result states
- Invalid or mismatched input
- Auth / permission boundaries
- Re-submission or idempotency behaviour
- Any AC item marked "(Pending)" or flagged as TBD

Render as a flat bulleted list (not a table) so it copy-pastes cleanly into
task managers that don't render markdown reliably.

---

## Open Questions

List anything that needs a decision before implementation can begin. Frame each
as a question, not a task. Include who is best placed to answer (e.g. "confirm
with backend lead", "check with design").

Omit this section if there are no blockers.

---

## Tone & Style Rules

- Write for a mixed audience: a QA or PM should understand every section.
- Avoid framework names, ORM methods, or architectural patterns unless the user
  explicitly works in a technical context and asked for that level of detail.
- "What Needs to Be Built" should read like a feature spec, not a code review. A PM or QA should be able to understand every bullet without knowing how it was implemented.
- Status ordering (Critical → Abnormal → Normal, or equivalent priority orderings)
  should be called out explicitly when sorting/ordering is part of the feature.
- If a behaviour is marked as out of scope or pending in the original ticket,
  note it clearly rather than silently omitting it.

---

## Quality Checklist (self-review before responding)

- [ ] Every requirement from the original ticket is reflected somewhere in the output
- [ ] Acceptance Criteria covers both the happy path and all relevant edge cases
- [ ] No section is padded — if a section has nothing to say, omit it
- [ ] Open Questions are genuine blockers, not implementation details
- [ ] The write-up could be handed to a QA to write test cases from
