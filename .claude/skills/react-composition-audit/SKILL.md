---
name: react-composition-audit
allowed-tools: Bash Read Grep Glob Agent
description: >
  Audit frontend/web/src for React composition defects that linters and
  typecheckers can't catch: hand-rolled markup that duplicates an existing
  components/ui/ primitive, and wrong element/ARIA semantics (clickable divs,
  navigation-as-button, missing type="button", missing selection-role
  semantics). Use as a periodic codebase sweep, before a design-system
  consolidation, or when the user asks whether components correctly reuse
  design-system primitives. Does NOT auto-commit — reports findings and
  applies only safe, unambiguous fixes to the working tree; anything requiring
  judgment is reported, not auto-fixed.
---

## Goal

Find real composition defects — call sites that should be using an existing
`components/ui/` primitive but aren't, and elements whose semantics don't
match what they do. This is not a "reuse everything" audit: a raw element is
often the *correct* choice, and flagging it anyway produces noise the user
will learn to ignore.

The calibration case: `frontend/web/src/components/PairwiseQuestion.tsx`'s
`ItemCard` renders a bare `<button>` with a scale/opacity transform for an
onboarding selection card. It strips every one of `Button`'s base classes
(background, padding, radius) and needs styling no `Button` variant exposes.
Reusing `Button` there would mean importing a component only to override
100% of what it provides — that is worse, not better. A well-calibrated run
against a healthy codebase should produce few or no `tier 1` (primitive
reuse) findings; don't manufacture them to fill out a report.

This skill covers exactly two things:

1. **Duplicated primitive markup** — a call site hand-rolls styling that an
   existing `components/ui/` primitive (or one of its variants) already
   provides.
2. **Element/ARIA semantics** — the DOM element doesn't match the
   interaction it implements (clickable `<div>` instead of `<button>`,
   navigation implemented as `<button onClick={navigate}>` instead of a
   router `Link`, a selection control that should expose `role="radio"` /
   `role="checkbox"` state, a non-submit `<button>` inside a `<form>` missing
   `type="button"`).

It explicitly does **not** cover prop-drilling, context usage, component
size/complexity, or general reusability — `code-review` already owns those.
This skill differs from a diff-scoped review by being a whole-codebase sweep
anchored on reading every `ui/` primitive's actual API first.

---

## Step 1 — Inventory the primitives

Read every file in `frontend/web/src/components/ui/`. For each primitive,
record:

- Its base classes (the `tv()` `base` key, or equivalent shared styling).
- Its variants and what each one changes.
- What it does *not* expose — no variant is a promise nothing outside those
  variants is supported. If a primitive has `variant: primary | secondary`
  and nothing else, "supports a `variant` prop" is the entire surface area.

This inventory is the anchor for every judgment in Step 3 — a finding is
only real if it points at a specific primitive whose actual (not imagined)
API already covers the call site's needs.

## Step 2 — Scan for candidates

From `frontend/web/src/`, gather candidates (don't judge yet, just collect):

```bash
# Raw interactive elements outside components/ui/ itself
grep -rn "<button" frontend/web/src --include="*.tsx" | grep -v "/components/ui/"
grep -rn "onClick" frontend/web/src --include="*.tsx" | grep -v "/components/ui/"

# Clickable non-interactive elements (likely semantics defect)
grep -rzn "<div[^>]*onClick" frontend/web/src --include="*.tsx"
grep -rzn "<span[^>]*onClick" frontend/web/src --include="*.tsx"

# Buttons inside forms (type="button" check)
grep -rln "<form" frontend/web/src --include="*.tsx"
```

For a full audit, spawn one Explore or general-purpose agent per top-level
route/screen directory to gather candidates in parallel; for a scoped check
(e.g. "review this component"), just read the file directly.

## Step 3 — Judge each candidate

For every candidate, judge against two independent questions. A candidate
can fail one, both, or neither — don't conflate them into a single verdict.

### 3a — Should this reuse a `ui/` primitive?

Compare the call site's actual classes/styling against the inventory from
Step 1:

- **Flag (tier 1 finding)** only when the call site's styling is a subset of
  — or directly matches — an existing primitive's base classes or an
  existing variant, and the call site isn't overriding or stripping most of
  what that primitive provides. This is the common, boring case: someone
  wrote `className="rounded-lg px-4 py-2 text-sm font-medium bg-ink
  text-paper"` by hand instead of `<Button variant="primary">`.
- **Do not flag** when the call site strips most of the primitive's base
  classes (e.g. `border-0 bg-transparent p-0`) or needs styling no variant
  exposes (custom transforms, card-like layouts, selection-state visuals).
  Forcing reuse here fights the primitive rather than benefiting from it.
  If you want to record that you checked, note it as a `correct-by-design`
  item with a one-line reason — this keeps the report legible as thorough
  rather than silent, without inflating severity.

Signal strength here is the whole game: only flag when you can name the
specific primitive and variant that already covers the need. "This could
maybe use a shared component" without pointing at one that actually fits is
not a finding.

### 3b — Are the element/ARIA semantics right?

Ask what the interaction actually does, not what element it happens to use:

- **Commits an action immediately** (click → side effect now) → `<button>`
  is correct. This includes selection cards that call a handler and disable
  themselves, like `ItemCard` — no `role="radio"` needed unless the
  selection is staged and submitted later as a group.
- **Sets a selection in a group, submitted later** → the group needs
  `role="radio"`/`role="checkbox"` semantics (native `<input>` or an
  ARIA-complete custom widget), not a plain `<button>` per option.
- **Navigates to a different route/URL** → should be a router `Link` (or
  `<a>`), not a `<button>` with an `onClick` navigate call — keyboard
  behavior, right-click/open-in-new-tab, and crawlability all depend on it
  being a real link.
- **Non-submit `<button>` inside a `<form>`** with no explicit `type` →
  defaults to `type="submit"` and will trigger form submission on click.
  This is a real, reliably-detectable bug, not a judgment call.
- **`<div>`/`<span>` with `onClick`** but no `role="button"`, `tabIndex`, or
  keyboard handler → not reachable by keyboard, not announced by screen
  readers. Flag regardless of visual styling.

For both 3a and 3b, read enough surrounding context (parent component, what
`onPick`/`onChoose`/handler props actually do) to judge intent — grep output
alone is not enough to classify a candidate.

## Step 4 — Rate severity and report

Severity mirrors `ui-ux-review`'s scale, calibrated for composition defects
specifically:

- **blocker** — element is unreachable by keyboard/screen reader, or a stray
  `<button>` inside a form causes unintended submission.
- **high** — navigation implemented as button (breaks middle-click/new-tab/
  crawlability) on a primary flow.
- **medium** — duplicated primitive markup (tier 1) on a component used in
  more than one place — the drift will compound.
- **low** — duplicated primitive markup on a single, unlikely-to-repeat call
  site.
- **nit** — cosmetic class-ordering or minor duplication with no functional
  difference.

### Fixes vs. findings-only

Apply a fix directly (Edit) only when it is unambiguous and low-risk:

- Adding `type="button"` to a non-submit button in a form.
- Swapping a clickable `<div>`/`<span>` for a `<button>` when there's no
  other reason it isn't one already (no conflicting layout/semantics).
- Swapping a `<button onClick={navigate}>` for the router's `Link` when the
  navigation target is static.

Leave everything else — especially any tier 1 primitive-reuse finding — as a
reported finding, not an auto-fix. Whether a call site should adopt a
primitive is a design judgment the user should confirm; silently rewriting
markup here risks fighting a primitive's variant API in ways that are hard
to review as a diff.

After applying any fixes, run `pnpm run lint && pnpm run typecheck` from
`frontend/web/` to confirm nothing broke, and remind the user no commit was
made.

### Report format

```
## React Composition Audit — <scope>

### Blocker
- [semantics] <file:line> — <what's wrong> → <fix or fixed>

### High
- ...

### Medium
- ...

### Low / Nit
- ...

### Correct-as-is (checked, no defect)
- <file:line> — <primitive considered> — <why it doesn't fit>

<N> findings, <M> fixed automatically, <K> left for review across <P> files.
```

If no findings survive Step 3, report `No composition issues found` plus
which primitives and which directories were checked — don't leave the
reviewer guessing what was covered.
