---
name: accessibility-review
allowed-tools: Bash Read Grep Glob Edit Agent
description: 'Audit web UI for WCAG 2.2 AA defects; report with criteria and severity, apply safe fixes only.'
---

## Goal

Catch accessibility defects that linters and typecheckers can't: missing
accessible names, keyboard traps, contrast failures against this repo's
actual design tokens, and screen-reader-invisible content. This is not a
"add ARIA everywhere" audit — over-labeling is itself a defect (A2 in
`references/patterns.md`). A well-calibrated run on a healthy screen produces few or no
blocker/high findings — don't manufacture severity to fill out a report.

**Calibration case**: a list-row thumbnail written as
`<div style={{ backgroundImage: ... }} />`, not an `<img>`, renders a
product photo with zero accessible name reachable by a screen reader (WCAG
1.1.1). Icon-only `<button>`s in the same row that carry
`aria-label="Dismiss item"` / `aria-label={saved ? 'Unsave' : 'Save'}` get
it right. Use the second pattern as the bar for "acceptable icon-only
control"; use the first as the bar for "this is a real finding," not a
nitpick.

This skill is **web-only**, scoped to the project's web frontend source
(`<frontend-src>`: the `src/` of the directory with a `package.json` that holds
the React + Tailwind UI; find it first and stop and ask if you cannot, since an
empty grep is not a clean audit). It audits JSX/TSX markup, ARIA attributes, and utility-class
color-token contrast — not React Native accessibility props
(`accessibilityLabel`, `accessibilityRole`, etc.), which are out of scope.

**Project specifics live in the project, not here.** Before scanning, read
the project's design-token table (usually the web frontend's `CLAUDE.md`),
any contrast or accessibility ADR, and an "Accessibility review notes"
section there if one exists. They hold the token values, the contrast
numbers, the known-bad literals and the calibration examples for this
codebase. This skill carries no token values of its own; if the project has
no such doc, compute contrast from the project's actual token source
(theme CSS / tokens file) with a contrast tool.

---

## Invocation

Accepts one of:

- **A component/screen file path or directory** — read the source directly.
- **Nothing specific** — full sweep across `<frontend-src>`.

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

From `<frontend-src>`, gather candidates per issue category (don't judge
yet, just collect):

```bash
# Semantic HTML — landmark elements and heading hierarchy
grep -rn "<nav\|<main\|<aside\|<footer\|<header" <frontend-src> --include="*.tsx"
grep -rn "<h[1-6]" <frontend-src> --include="*.tsx"

# Semantic HTML — custom div/span widgets standing in for native form controls
grep -rnE "<(div|span)[^>]*onClick" <frontend-src> --include="*.tsx"

# ARIA — icon-only buttons, check each has aria-label
grep -rn "<button" <frontend-src> --include="*.tsx" -A 4 | grep -B 4 "<Icon"

# ARIA — dynamic/async content that should announce via aria-live
grep -rln "useMutation\|useQuery" <frontend-src> --include="*.tsx"
grep -rn "aria-live\|role=\"status\"\|role=\"alert\"" <frontend-src> --include="*.tsx"

# ARIA — dialogs/modals, check for aria-modal + focus management
grep -rln "role=\"dialog\"" <frontend-src> --include="*.tsx"

# Keyboard navigation — positive tabIndex (breaks natural tab order)
grep -rn "tabIndex={[1-9]" <frontend-src> --include="*.tsx"

# Keyboard navigation — onKeyDown handlers that might trap/intercept Tab or Escape
grep -rn "onKeyDown\|onKeyPress" <frontend-src> --include="*.tsx"

# Color & contrast — small text on the project's low-emphasis text tokens
# (names from the project's design-token table; contrast risk, see A5 in `references/patterns.md`)
grep -rn "text-<muted-token>" <frontend-src> --include="*.tsx" | grep -E "text-\[(9|10|11|12)px\]"
grep -rn "text-<placeholder-token>" <frontend-src> --include="*.tsx"
# ...and hardcoded colour literals that bypass the token utility entirely
grep -rnE "#[0-9a-fA-F]{6}\b" <frontend-src> --include="*.tsx"

# Screen reader support — <img> alt text and background-image "photo" divs
grep -rn "<img" <frontend-src> --include="*.tsx"
grep -rn "backgroundImage:" <frontend-src> --include="*.tsx"

# Screen reader support — form inputs and label association
grep -rln "<input\|<Input\|<textarea\|<select\|PasswordInput" <frontend-src> --include="*.tsx"
grep -rn "<label\|htmlFor=" <frontend-src> --include="*.tsx"

# Screen reader support — error messages linked to inputs
grep -rn "aria-describedby\|aria-invalid" <frontend-src> --include="*.tsx"

# Motion & reduced motion
grep -rn "animate-\|transition-\|@keyframes" <frontend-src> --include="*.tsx" --include="*.css"
grep -rn "prefers-reduced-motion\|matchMedia" <frontend-src> --include="*.tsx" --include="*.ts" --include="*.css"

# Touch & target size — icon-only interactive elements under 24px (size-N = N*4px in Tailwind v4)
grep -rn "size-[1-5]\b" <frontend-src> --include="*.tsx"
```

For a full audit, run these per top-level directory inside the spawned
agents rather than once globally — keeps each agent's context focused on
files it will actually judge.

## Step 3 — Judge each candidate

Read `references/patterns.md` first (A1–A8: the recurring accessible-name gaps,
ARIA overuse, focus management, live regions, contrast, reduced motion, touch
targets, navigation vs. button). If missing, read
`$HOME/.claude/skills/accessibility-review/references/patterns.md`.

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
| Color & contrast | Text token pairs from the project's design-token table used below the 4.5:1 (normal text) / 3:1 (large text, ≥18px or ≥14px bold) thresholds; color as the only differentiator (e.g. red text with no icon/label for an error) | A low-emphasis text token on the page background at a small size (e.g. 10px eyebrow labels) — compute the ratio from the project's real token values and check it, don't assume an established pattern passes. Also flag any hardcoded gray literal that bypasses the token utility class | 1.4.1, 1.4.3 |
| Screen reader | `<img>` without meaningful `alt`; a `backgroundImage` div carrying content (not decoration) with no accessible name; form input with no associated `<label>`/`aria-label`; error text not linked via `aria-describedby` | Content-bearing image (product photo, not a pure background pattern) with no text alternative anywhere in the DOM | 1.1.1, 3.3.1, 4.1.2 |
| Motion | CSS animation/transition with no `prefers-reduced-motion` check, for anything beyond a ≤200ms opacity/color tap-feedback transition (`active:opacity-90`-style feedback is fine as-is — see A6 in `references/patterns.md`) | Auto-playing, non-essential animation that can't be paused/reduced | 2.3.3 (AAA, still worth flagging as `low`) |
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
`<frontend-project>/` to confirm nothing broke, and remind the user no commit was
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
