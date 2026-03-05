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

---

### Context

1–3 sentences explaining _why_ this subtask exists, what problem it solves, and
where it fits in the bigger feature. Mention relevant existing models, services,
or data sources. Written so a PM or QA can understand it without technical
background.

---

### What Needs to Be Built

A clear list of the concrete deliverables. For each item:

- State _what_ it is (route, component, service method, etc.)
- State _what it does_ in plain language
- Include key fields, parameters, or behaviours that are not obvious

Use a numbered or bulleted list. Avoid code blocks unless a route path or field
list genuinely aids clarity — and even then, keep them short.

---

### Edge Cases to Handle

A table of scenarios that require special handling. Columns:

| Case | Behaviour |

Pull edge cases from:

- Nullable fields mentioned in acceptance criteria
- Empty / zero-result states
- External service failures
- Pending / incomplete data states
- Any AC item marked "(Pending)" or flagged as TBD

---

### Open Questions

List anything that needs a decision before implementation can begin. Frame each
as a question, not a task. Include who is best placed to answer (e.g. "confirm
with backend lead", "check with design").

Omit this section if there are no blockers.

---

## Tone & Style Rules

- Write for a mixed audience: a QA or PM should understand every section.
- Avoid framework names, ORM methods, or architectural patterns unless the user
  explicitly works in a technical context and asked for that level of detail.
- "What Needs to Be Built" should read like a feature spec, not a code review.
- Status ordering (Critical → Abnormal → Normal, or equivalent priority orderings)
  should be called out explicitly when sorting/ordering is part of the feature.
- If a behaviour is marked as out of scope or pending in the original ticket,
  note it clearly rather than silently omitting it.

---

## Quality Checklist (self-review before responding)

- [ ] Every acceptance criterion is reflected somewhere in the output
- [ ] Nullable / optional fields are covered in Edge Cases
- [ ] No section is padded — if a section has nothing to say, omit it
- [ ] Open Questions are genuine blockers, not implementation details
- [ ] The write-up could be handed to a QA to write test cases from
