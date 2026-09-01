---
name: accessibility-review
allowed-tools: Bash Read Grep Glob Edit Agent
description: >
  Audit frontend/web/src for accessibility defects against WCAG 2.2 AA —
  semantic HTML, ARIA correctness, keyboard navigation, color contrast,
  screen reader support, reduced motion, and touch target size. Produces a
  report grouped by component with WCAG success criterion references,
  severity ratings, and code-level fix suggestions. Use during feature
  implementation, before PR review, or as a periodic accessibility sweep.
  Does NOT auto-commit — reports findings and applies only safe,
  unambiguous fixes to the working tree; anything requiring copy or design
  judgment is reported, not auto-fixed.
---

## Goal

Catch accessibility defects that linters and typecheckers can't: missing
accessible names, keyboard traps, contrast failures against this repo's
actual design tokens, and screen-reader-invisible content. This is not a
"add ARIA everywhere" audit — over-labeling is itself a defect (Appendix
A2). A well-calibrated run on a healthy screen produces few or no
blocker/high findings — don't manufacture severity to fill out a report.

**Calibration case**: `components/ui/FeedRow.tsx`'s item thumbnail is a
`<div style={{ backgroundImage: ... }} />`, not an `<img>` — it renders the
product photo with zero accessible name reachable by a screen reader (WCAG
1.1.1). The same file's dismiss/save buttons *do* get this right —
`aria-label="Dismiss item"` / `aria-label={savedState ? 'Unsave' : 'Save'}`
on icon-only `<button>`s. Use the second pattern as the bar for "acceptable
icon-only control"; use the first as the bar for "this is a real finding,"
not a nitpick.

This skill is **web-only**, scoped to `frontend/web/src` (React 19 + Vite +
Tailwind v4 + TanStack Router, per `frontend/web/CLAUDE.md`). It audits
JSX/TSX markup, ARIA attributes, and Tailwind color-token contrast — not
React Native accessibility props (`accessibilityLabel`, `accessibilityRole`,
etc.), which are a `frontend/mobile` concern and out of scope here.

---

## Invocation

Accepts one of:

- **A component/screen file path or directory** — read the source directly.
- **Nothing specific** — full sweep across `frontend/web/src`.

## Step 1 — Scope the review

Identify whether this is a **quick check** (single component, e.g. during
feature review) or a **full audit** (periodic sweep across the app). For a
full audit, spawn one Explore or general-purpose agent per top-level
directory (`screens/`, `components/`, `routes/`) to gather
candidates in parallel, each given Step 2's grep patterns and Step 3's
judgment criteria, and asked to return findings in the Report Format below.
For a quick check on one component, review it directly without spawning
agents.

## Step 2 — Scan for candidates

From `frontend/web/src`, gather candidates per issue category (don't judge
yet, just collect):

```bash
# Semantic HTML — landmark elements and heading hierarchy
grep -rn "<nav\|<main\|<aside\|<footer\|<header" frontend/web/src --include="*.tsx"
grep -rn "<h[1-6]" frontend/web/src --include="*.tsx"

# Semantic HTML — custom div/span widgets standing in for native form controls
grep -rnE "<(div|span)[^>]*onClick" frontend/web/src --include="*.tsx"

# ARIA — icon-only buttons, check each has aria-label
grep -rn "<button" frontend/web/src --include="*.tsx" -A 4 | grep -B 4 "<Icon"

# ARIA — dynamic/async content that should announce via aria-live
grep -rln "useMutation\|useQuery" frontend/web/src --include="*.tsx"
grep -rn "aria-live\|role=\"status\"\|role=\"alert\"" frontend/web/src --include="*.tsx"

# ARIA — dialogs/modals, check for aria-modal + focus management
grep -rln "role=\"dialog\"" frontend/web/src --include="*.tsx"

# Keyboard navigation — positive tabIndex (breaks natural tab order)
grep -rn "tabIndex={[1-9]" frontend/web/src --include="*.tsx"

# Keyboard navigation — onKeyDown handlers that might trap/intercept Tab or Escape
grep -rn "onKeyDown\|onKeyPress" frontend/web/src --include="*.tsx"

# Color & contrast — small/eyebrow text on the mute token (contrast risk, see Appendix A)
grep -rn "text-mute" frontend/web/src --include="*.tsx" | grep -E "text-\[(9|10|11|12)px\]"
grep -rn "text-mute-2\|text-paper-3" frontend/web/src --include="*.tsx"

# Screen reader support — <img> alt text and background-image "photo" divs
grep -rn "<img" frontend/web/src --include="*.tsx"
grep -rn "backgroundImage:" frontend/web/src --include="*.tsx"

# Screen reader support — form inputs and label association
grep -rln "<input\|<Input\|<textarea\|<select\|PasswordInput" frontend/web/src --include="*.tsx"
grep -rn "<label\|htmlFor=" frontend/web/src --include="*.tsx"

# Screen reader support — error messages linked to inputs
grep -rn "aria-describedby\|aria-invalid" frontend/web/src --include="*.tsx"

# Motion & reduced motion
grep -rn "animate-\|transition-\|@keyframes" frontend/web/src --include="*.tsx" --include="*.css"
grep -rn "prefers-reduced-motion\|matchMedia" frontend/web/src --include="*.tsx" --include="*.ts" --include="*.css"

# Touch & target size — icon-only interactive elements under 24px (size-N = N*4px in Tailwind v4)
grep -rn "size-[1-5]\b" frontend/web/src --include="*.tsx"
```

For a full audit, run these per top-level directory inside the spawned
agents rather than once globally — keeps each agent's context focused on
files it will actually judge.

## Step 3 — Judge each candidate

For every candidate, read enough surrounding context (parent component,
what the click handler does, whether a sibling element already provides an
accessible name) to judge intent — grep output alone is not enough to
classify a candidate. Map each finding to the WCAG 2.2 success criterion it
violates using the table below; if none fit, it isn't a WCAG finding (it may
still belong in `ui-ux-review` instead).

| Category | What to look for | Blocking signal | WCAG SC |
|---|---|---|---|
| Semantic HTML | Missing/duplicated landmark elements; heading levels that skip (h1→h3); a `<div onClick>` standing in for a native control | Interactive `<div>`/`<span>` with no `role`, no `tabIndex`, no keyboard handler | 1.3.1, 4.1.2 |
| ARIA | Icon-only `<button>` with no `aria-label`; redundant `aria-label` restating the role (e.g. `aria-label="Save button"` on a `<button>`); wrong/absent `role` | Icon-only control with **zero** accessible name (no `aria-label`, no visible text) | 4.1.2 |
| ARIA — live regions | Async mutation success/error with no `aria-live`/`role="status"`/`role="alert"` announcement | Error state after a form submit that's silent to screen readers | 4.1.3 |
| Keyboard | Positive `tabIndex`; `onKeyDown` that swallows Tab/Escape; a `role="dialog"` with no focus moved into it on open and no Escape-to-close | Focus trap (can't Tab or Escape out); dialog leaves focus behind the overlay | 2.1.1, 2.1.2, 2.4.3 |
| Color & contrast | Text token pairs from `frontend/web/CLAUDE.md`'s design table used below the 4.5:1 (normal text) / 3:1 (large text, ≥18px or ≥14px bold) thresholds; color as the only differentiator (e.g. red text with no icon/label for an error) | `text-mute` (`#8A8A8A`) on `bg-paper` (`#FAF8F5`) computes to roughly 3.2:1 — below 4.5:1 for any use under ~18px. Every eyebrow-label use of `text-mute` at `text-[10px]` (the pattern in `FeedRow`, `FeedScreen`, `AdminScreen`, `YouScreen`) is a real candidate — verify with a contrast tool, don't just take this note's number as final | 1.4.1, 1.4.3 |
| Screen reader | `<img>` without meaningful `alt`; a `backgroundImage` div carrying content (not decoration) with no accessible name; form input with no associated `<label>`/`aria-label`; error text not linked via `aria-describedby` | Content-bearing image (product photo, not a pure background pattern) with no text alternative anywhere in the DOM | 1.1.1, 3.3.1, 4.1.2 |
| Motion | CSS animation/transition with no `prefers-reduced-motion` check, for anything beyond a ≤200ms opacity/color tap-feedback transition (`active:opacity-90`-style feedback is fine as-is — see Appendix A) | Auto-playing, non-essential animation that can't be paused/reduced | 2.3.3 (AAA, still worth flagging as `low`) |
| Touch target | Interactive element smaller than `size-6` (24px) with no padding/hit-area compensation; two adjacent interactive elements with <8px gap | Primary interactive control (not a rare/secondary one) under 24×24px | 2.5.8 |

## Step 4 — Rate severity

Severity mirrors `ui-ux-review`'s and `react-composition-audit`'s scale,
calibrated for accessibility defects specifically — weight by how many
users are fully blocked, not just by WCAG conformance level:

- **blocker** — a user relying on keyboard or screen reader cannot complete
  a primary flow at all (keyboard trap, content-bearing image/button with no
  accessible name on a primary action, dialog that traps focus with no
  Escape).
- **high** — the element is reachable but the interaction is broken or
  seriously degraded (contrast failure on body/eyebrow text used
  app-wide, missing `aria-live` on a form's error state, heading hierarchy
  that breaks screen-reader navigation on a content-heavy screen).
- **medium** — noticeable but works around itself (redundant ARIA labeling,
  a secondary icon-only control missing a label, touch target slightly
  under 24px on a rarely-used control).
- **low** — AAA-level or comfort issues (motion not respecting
  `prefers-reduced-motion` on a purely decorative animation).
- **nit** — cosmetic ARIA redundancy with no functional difference.

### Fixes vs. findings-only

Apply a fix directly (Edit) only when it is mechanical and carries no
copy/design judgment:

- Down-leveling a positive `tabIndex` (e.g. `tabIndex={3}` → `tabIndex={0}`
  or removing it) — never changes wording or layout, only tab order.
- Wiring a matching `id`/`htmlFor` pair when a `<label>` sits immediately
  adjacent to an `<input>`/`<select>`/`<textarea>` with no association —
  purely mechanical linkage, the label text itself is untouched.
- Adding `aria-hidden="true"` to a decorative icon that sits directly beside
  visible text already providing the same accessible name (avoids
  double-announcement) — only when that sibling text genuinely covers it;
  if the icon carries information the text doesn't, this is not safe.

Leave everything else — new `aria-label` wording, `alt` text content, color
token swaps for contrast, heading restructuring, focus-management additions
to dialogs, `prefers-reduced-motion` guards — as a reported finding, not an
auto-fix. Writing an accessible name or choosing a replacement color is a
judgment call the user should confirm; silently inventing copy or
restyling a screen here produces a diff that's hard to review as "safe."

After applying any fixes, run `pnpm run lint && pnpm run typecheck` from
`frontend/web/` to confirm nothing broke, and remind the user no commit was
made.

## Step 5 — Report

Group findings by component so the reviewer can act file-by-file, not
heuristic-by-heuristic. Within a component, list findings most-severe
first, each tagged with its WCAG success criterion.

### Report format

```
## Accessibility Review — <scope>

### <ComponentName> (<file path>)
- **[blocker]** WCAG 1.1.1 — <file:line> — <what's wrong> → <fix or fixed>
- **[high]** WCAG 1.4.3 — <file:line> — <what's wrong> → <fix or fixed>

### <NextComponent> (<file path>)
- ...

### Correct-as-is (checked, no defect)
- <file:line> — <pattern considered> — <why it already passes>

<N> findings across <M> components. <K> fixed automatically, <J> left for
review.
```

If no findings survive Step 4, report `No accessibility issues found` plus
which categories and directories were checked — don't leave the reviewer
guessing what was covered.

---

## Appendix A — Web accessibility patterns for this codebase

### A1. Accessible names — the recurring gap

Every interactive or content-bearing element needs an accessible name from
*one* of: visible text, `alt`, `aria-label`, or `aria-labelledby`. Never
more than one at once saying the same thing (redundant), never zero
(invisible to assistive tech).

```tsx
// Bad — FeedRow-style calibration case: content-bearing image, no name anywhere
<div
  className="bg-paper-2 h-30 w-24 shrink-0 bg-cover bg-center"
  style={{ backgroundImage: `url(${item.image_url})` }}
/>

// Good — role="img" + aria-label, or a real <img> with alt
<div
  role="img"
  aria-label={item.name}
  className="bg-paper-2 h-30 w-24 shrink-0 bg-cover bg-center"
  style={{ backgroundImage: `url(${item.image_url})` }}
/>
```

```tsx
// Good — the pattern already used correctly in FeedRow's icon-only controls
<button type="button" aria-label="Dismiss item" onClick={handleDismiss}>
  <Icon name="x" size={16} />
</button>
```

### A2. ARIA overuse is also a defect

Adding `aria-label` or `role` to every element creates noise that drowns
real content — this skill should not flag a plain layout `<div>` for
"missing a role." Only flag elements that are interactive or convey
content and have no name at all. A `<button>` whose visible text already
says "Save" doesn't need `aria-label="Save button"` — that produces
"Save button, button" for a screen reader user.

### A3. Keyboard and dialog focus management

```tsx
// Current pattern in YouScreen's ResetConfirmModal — correct role/aria-modal,
// but no focus is moved into the dialog on open and no Escape handler exists.
// This is exactly the kind of gap this skill should flag as `blocker`:
// a keyboard-only user tabbing through the page behind the overlay can
// still reach controls hidden under it.
<div role="dialog" aria-modal="true" aria-label="Reset my style" className="fixed inset-0 ...">
  ...
</div>

// Fix direction (not auto-applied — requires deciding where focus returns):
// useEffect(() => { dialogRef.current?.focus() }, [])
// onKeyDown={(e) => { if (e.key === 'Escape') onCancel() }}
```

### A4. Live regions for async state

```tsx
// Good — the pattern already used correctly in YouScreen's SuccessToast
<div role="status" aria-live="polite">
  <span>Style reset — taste updated.</span>
</div>
```

Use `role="status"`/`aria-live="polite"` for non-urgent confirmations
(saved, updated). Reserve `role="alert"`/`aria-live="assertive"` for
errors that block the user's next action (failed form submit). Never
apply live regions to content that changes purely for visual/animation
reasons.

### A5. Color contrast against this repo's actual tokens

Verify pairs from `frontend/web/CLAUDE.md`'s design-token table, not
Tailwind's default gray scale (the repo bans raw `gray-*` anyway). Known
risk to check first: `text-mute` (`#8A8A8A`) on `bg-paper` (`#FAF8F5`)
sits close to the 4.5:1 line and reads as **below** it at small sizes —
every `text-[10px] ... text-mute` eyebrow label (store names, section
labels, timestamps) is worth verifying with a contrast checker rather than
assumed to pass because it's an established pattern. `text-mute-2`
(`#B8B5AF`, placeholder/disabled) on `bg-paper` is lower contrast still —
acceptable *only* on genuinely disabled controls (WCAG exempts disabled
content), not on any readable label.

### A6. Reduced motion

```css
/* Good direction — gate non-essential animation */
@media (prefers-reduced-motion: reduce) {
  .animate-pulse { animation: none; }
}
```

The repo's `active:opacity-90` / `active:bg-terracotta-press` tap-feedback
transitions (≤200ms, functional press feedback) are fine as-is — don't
flag them. Flag animation used for decoration (entrance transitions,
onboarding pick scale/opacity per `frontend/web/CLAUDE.md`'s "Motion"
section, `animate-pulse` skeleton loaders left running indefinitely) that
has no `prefers-reduced-motion` guard.

### A7. Touch target size (WCAG 2.2, 2.5.8)

Tailwind v4's `size-N` utility is `N × 4px` (`size-11` = 44px, `size-6` =
24px). The repo already clears this in most icon-only controls — `FeedRow`
dismiss (`size-11`) and save (`size-8`) buttons both clear 24px. Flag any
new icon-only interactive element under `size-6` with no compensating
padding, and any two adjacent interactive elements with less than 8px gap.

### A8. Navigation vs. button semantics

Cross-reference `react-composition-audit` before flagging: that skill
already owns "navigation implemented as button" findings (see issue #092,
closed). This skill should still flag the accessibility *consequence* of
navigation-as-button when it also drops an accessible state — e.g.
`TabBar`'s active-tab `<Link>` has no `aria-current="page"`, so a screen
reader user tabbing through the tab bar gets no indication of which tab is
currently selected (WCAG 4.1.2/1.3.1) — but leave the element-choice
finding itself (`<button>` vs `Link`) to `react-composition-audit` to avoid
duplicate, conflicting reports on the same line.
