# Web accessibility patterns

## A1. Accessible names — the recurring gap

Every interactive or content-bearing element needs an accessible name from
*one* of: visible text, `alt`, `aria-label`, or `aria-labelledby`. Never
more than one at once saying the same thing (redundant), never zero
(invisible to assistive tech).

```tsx
// Bad — calibration case: content-bearing image, no name anywhere
<div
  className="h-30 w-24 shrink-0 bg-cover bg-center"
  style={{ backgroundImage: `url(${item.image_url})` }}
/>

// Good — role="img" + aria-label, or a real <img> with alt
<div
  role="img"
  aria-label={item.name}
  className="h-30 w-24 shrink-0 bg-cover bg-center"
  style={{ backgroundImage: `url(${item.image_url})` }}
/>
```

```tsx
// Good — an icon-only control with an accessible name
<button type="button" aria-label="Dismiss item" onClick={handleDismiss}>
  <Icon name="x" size={16} />
</button>
```

## A2. ARIA overuse is also a defect

Adding `aria-label` or `role` to every element creates noise that drowns
real content — this skill should not flag a plain layout `<div>` for
"missing a role." Only flag elements that are interactive or convey
content and have no name at all. A `<button>` whose visible text already
says "Save" doesn't need `aria-label="Save button"` — that produces
"Save button, button" for a screen reader user.

## A3. Keyboard and dialog focus management

```tsx
// A modal with correct role/aria-modal, but no focus is moved into the
// dialog on open and no Escape handler exists.
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

## A4. Live regions for async state

```tsx
// Good — a success toast announced politely
<div role="status" aria-live="polite">
  <span>Style reset — taste updated.</span>
</div>
```

Use `role="status"`/`aria-live="polite"` for non-urgent confirmations
(saved, updated). Reserve `role="alert"`/`aria-live="assertive"` for
errors that block the user's next action (failed form submit). Never
apply live regions to content that changes purely for visual/animation
reasons.

## A5. Color contrast against the project's actual tokens

Verify pairs from the project's design-token table, not the framework's
default gray scale. Check first: the low-emphasis text token (metadata,
captions, timestamps) on every background it is rendered on, especially at
small sizes — each tiny eyebrow label is worth verifying with a contrast
checker rather than assumed to pass because it's an established pattern.
Placeholder/disabled tokens are acceptable *only* on genuinely disabled
controls (WCAG exempts disabled content), not on any readable label. When a
token has been corrected after a contrast failure, the lasting risk is a
hardcoded literal (an older value of the same token) that bypasses the
utility class and silently keeps failing — grep for those literals before
assuming every label inherits the current token.

## A6. Reduced motion

```css
/* Good direction — gate non-essential animation */
@media (prefers-reduced-motion: reduce) {
  .animate-pulse { animation: none; }
}
```

Short functional press-feedback transitions (≤200ms, e.g. `active:opacity-90`)
are fine as-is — don't flag them. Flag animation used for decoration
(entrance transitions, selection scale/opacity per the project's motion
rules, `animate-pulse` skeleton loaders left running indefinitely) that has
no `prefers-reduced-motion` guard.

## A7. Touch target size (WCAG 2.2, 2.5.8)

Tailwind v4's `size-N` utility is `N × 4px` (`size-11` = 44px, `size-6` =
24px). Flag any new icon-only interactive element under `size-6` with no
compensating padding, and any two adjacent interactive elements with less
than 8px gap.

## A8. Navigation vs. button semantics

Cross-reference `react-composition-audit` before flagging: that skill
already owns "navigation implemented as button" findings (see issue #092,
closed). This skill should still flag the accessibility *consequence* of
navigation-as-button when it also drops an accessible state — e.g.
a tab bar's active `<Link>` has no `aria-current="page"` (check first —
most router `Link`s set it automatically), so a screen
reader user tabbing through the tab bar gets no indication of which tab is
currently selected (WCAG 4.1.2/1.3.1) — but leave the element-choice
finding itself (`<button>` vs `Link`) to `react-composition-audit` to avoid
duplicate, conflicting reports on the same line.
