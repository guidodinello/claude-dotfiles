---
name: figma-to-tailwind
description: Implement UI components from Figma designs using semantic HTML, Tailwind 4, and tailwind-variants (tv()) following project conventions
---

# Figma to Tailwind

Reference guide for translating Figma designs into production-ready components with semantic HTML, Tailwind 4, and `tailwind-variants`.

---

## Semantic HTML

| Element | Use when |
|---|---|
| `<article>` | Self-contained, independently distributable content (cards, posts, products) |
| `<section>` | Thematic grouping **with its own heading** — not for layout grouping |
| `<div>` | Pure layout grouping with no semantic meaning |
| `<button>` | Actions that don't navigate (modals, sidebars, triggering logic) |
| `<a>` | Navigation to a URL — always include `href` |

- If reaching for `<section>` just to group layout rows inside a card, use `<div>` instead
- Never use `<h1>` inside a repeated card — only one `<h1>` per page. Use `<h3>` or lower inside cards; when in doubt, use `<p>` with text styles

---

## Flexbox Patterns

### `flex-1` vs `justify-between`

Row with one growing element + one fixed element (title + icon button):

- ✅ `flex-1` on the growing element — targeted, survives adding a third child
- ❌ `justify-between` on the container — spreads all children, breaks with 3+ elements

### Flex column next to a fixed sibling

Always pair both utilities:

```tsx
content: "flex flex-1 min-w-0 flex-col ..."
```

- `flex-1` — fills remaining horizontal space
- `min-w-0` — allows shrinking below natural content width, preventing overflow

### Image + content rows

Set `items-start` on the row container — `items-stretch` (default) distorts the image wrapper when content is taller:

```tsx
body: "flex flex-row gap-3 items-start"
```

---

## Image Sizing

Always constrain images via their **wrapper**, not the `<img>` tag:

```tsx
<div className="w-[120px] shrink-0 aspect-[10/13] overflow-hidden rounded-lg">
  <img className="w-full h-full object-cover" />
</div>
```

- `w-*` + `aspect-*` on the wrapper
- `shrink-0` prevents compression in flex rows
- `overflow-hidden` + `rounded-*` on the wrapper clips to border radius
- `object-cover` on `<img>` fills the box without distortion
- Derive aspect ratio from Figma: `width / height` → `120 × 156` → `aspect-[10/13]`

---

## Figma Token Mapping

Prefer native Tailwind 4 scale values over arbitrary ones.

### Spacing

| Figma token | px | Tailwind |
|---|---|---|
| Space/1 | 4px | `gap-1` / `p-1` |
| Space/2 | 8px | `gap-2` / `p-2` |
| Space/3 | 12px | `gap-3` / `p-3` |
| Space/4 | 16px | `gap-4` / `p-4` |

### Typography

| Figma token | Tailwind |
|---|---|
| Font Styles/SM | `text-sm` |
| Font Styles/Base | `text-base` |
| Font Styles/LG | `text-lg` |
| Font Styles/XL | `text-xl` |
| Font Weight/Regular | `font-normal` |
| Font Weight/Medium | `font-medium` |
| Font Weight/Bold | `font-bold` |

### Skip these Figma export properties

- `line-height` — only add `leading-none` when Figma explicitly says `100%`; otherwise leave as default
- `letter-spacing: 0.5%` — negligible, skip unless visually significant
- `leading-trim: NONE` — ignore
- `opacity: 1` — ignore (default)
- `angle: 0deg` — ignore

### Color tokens

| Figma token | Hex | Tailwind |
|---|---|---|
| Text-Neutral-Default | `#201E1C` | `text-neutral-900` |
| Text-Neutral-Secondary | `#36322F` | `text-neutral-700` |
| Border-Neutral-Tertiary | `#BBB7B3` | `border-neutral-300` |
| Neutral-0 | `#FFFFFF` | `bg-white` |

> Check `app.css` first — if the project defines custom CSS variables in a `@theme` block, prefer `text-(--token-name)` over hardcoded hex values.

---

## `tailwind-variants` (`tv()`)

### All styles go in slots — no mixing

Once using `tv()`, every style lives in a slot. Never mix raw `className` strings with slot calls on the same component:

```tsx
// ❌ mixed
<div className={styles.content()}>
  <h3 className="flex-1 text-lg font-medium text-neutral-900">...</h3>
</div>

// ✅ everything in slots
<h3 className={styles.title()}>...</h3>
```

### Remove dead slots

If a slot is defined in `tv()` but never referenced in JSX, delete it.

### Name slots semantically, not visually

| ❌ Visual name | ✅ Semantic name |
|---|---|
| `infoLink` | `infoButton` (it's a `<button>`, not an `<a>`) |
| `bigText` | `price` |
| `greyLabel` | `biomarkers` |

---

## Responsive Design

### Account for sidebar width at desktop breakpoints

Tailwind breakpoints are viewport-based, but content lives inside a layout with a sidebar (`md:pl-[280px]`) and section padding (`md:px-14` = 56px each side) — subtracting **~392px** from the viewport.

| Viewport | Sidebar | Padding | Available | 2 cols each |
|---|---|---|---|---|
| `lg` 1024px | 280px | 112px | 632px | ~308px ← too tight |
| `xl` 1280px | 280px | 112px | 888px | ~436px ← comfortable |

**Prefer `xl:grid-cols-2` over `lg:grid-cols-2`** in sidebar layouts.

Formula: `column width = (viewport − sidebar − section padding − gaps) / columns`

### Cards: stack on mobile, side-by-side on `sm+`

```tsx
body: "flex flex-col gap-3 sm:flex-row sm:items-start",
imageWrapper: "aspect-video w-full shrink-0 overflow-hidden rounded-lg sm:aspect-[10/13] sm:w-[120px]",
```

- Mobile (< 640px): full-width `aspect-video` banner on top, text below at 100% width
- `sm+`: 120px portrait image left, text right — matches Figma design

Never use `flex-row` with a fixed-width image as the default — on a 344px screen with 120px image + 32px padding, text collapses to ~148px.

### `leading-none` is only safe for single-line text

`leading-none` sets `line-height: 1`. Only use on guaranteed single-line text (price, badge, short label). For titles, descriptions, or any copy that may wrap, use `leading-snug` or `leading-normal`:

```tsx
// ❌ breaks on long titles
title: "text-lg font-medium leading-none",

// ✅
title: "text-lg font-medium leading-snug",
```

### `items-start` in rows with multi-line content

When a flex row has a potentially multi-line element (title, description) next to a short inline element (button, badge, icon), use `items-start` — not `items-center`:

```tsx
// ❌ button jumps to vertical center of a 4-line title
titleRow: "flex items-center gap-2",

// ✅ button pins to the top
titleRow: "flex items-start gap-2",
```

### `shrink-0` on fixed inline elements

Any small, fixed-size element in a flex row next to a `flex-1` sibling must have `shrink-0`:

```tsx
// Applies to: icon buttons, status badges, avatars, price labels, "Info ›" links
infoButton: "flex shrink-0 items-center gap-1 text-sm font-medium",
```

---

## Pre-Ship Checklist

- [ ] Tested at 344px (Galaxy Z Fold 5) — no overflow, no collapsed text
- [ ] Tested at 375px (iPhone SE) — comfortable single-column layout
- [ ] Tested at 768px (iPad mini) — sidebar appears, content still readable
- [ ] Tested at 1024px (iPad Pro) — multi-column grid (if any) doesn't over-compress cards
- [ ] Title uses `leading-snug` or `leading-normal`, never `leading-none`
- [ ] Any inline button/badge/icon next to `flex-1` text has `shrink-0`
- [ ] Row containing multi-line text uses `items-start`, not `items-center`
- [ ] Grid breakpoint accounts for sidebar (`xl:` not `lg:` in sidebar layouts)
- [ ] All styles in `tv()` slots — no mixed raw `className` strings
- [ ] No dead (unused) slots in `tv()` definition
- [ ] Slot names are semantic, not visual
- [ ] Images sized via wrapper, not `<img>` tag directly
- [ ] Figma noise properties skipped (opacity: 1, angle: 0deg, etc.)
- [ ] Colors use CSS variables from `app.css` when available
