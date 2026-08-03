# React Native — Agent Code Guidelines

General-purpose guidelines for React Native projects where AI agents assist with development.

---

## Philosophy

- **TypeScript strict mode everywhere** — `strict: true` in tsconfig. No `any`, ever.
- **Minimal dependencies** — every dep is a maintenance burden. Prefer RN built-ins and stdlib before adding a library.
- **Mobile-first thinking** — touch targets ≥44pt, respect safe areas, handle keyboard avoidance, test on both iOS and Android.
- **No class components** — function components and hooks only.

---

## Tech Stack

<!-- TODO #05: fill in after scaffold decision -->
| Concern | Library |
|---------|---------|
| Framework | <!-- Expo managed workflow recommended --> |
| Navigation | <!-- React Navigation v7 recommended --> |
| State management | <!-- Zustand recommended --> |
| Server state / data fetching | <!-- TanStack Query recommended --> |
| Styling | NativeWind + tailwind-variants (`tv()`) |
| Package manager | pnpm |

---

## Component Conventions

- One component per file; file and component share the same name (`ItemCard.tsx` exports `ItemCard`).
- Props typed inline with `type Props = { ... }` — never use `React.FC<Props>`, just `function ItemCard({ ... }: Props)`.
- Extract sub-components into the same file only if they are not reused elsewhere; move to their own file the moment they are.

```tsx
// Good
type Props = {
  name: string
  price: number
  onPress: () => void
}

export function ItemCard({ name, price, onPress }: Props) {
  return (...)
}

// Bad
const ItemCard: React.FC<Props> = ({ name, price, onPress }) => (...)
```

---

## TypeScript

Use modern syntax — never import `React.FC`, `React.ReactNode` is fine as a return type when needed.

```tsx
// Good
function Screen(): React.ReactNode { ... }
function Button({ label }: { label: string }) { ... }

// Bad
const Screen: React.FC = () => { ... }
```

Use discriminated unions for component variants instead of boolean flags:

```tsx
// Good
type ButtonProps =
  | { variant: 'primary'; onPress: () => void }
  | { variant: 'ghost'; onPress: () => void; label: string }

// Bad
type ButtonProps = { primary?: boolean; ghost?: boolean; ... }
```

---

## Styling

Use **NativeWind** (Tailwind utility classes) + **tailwind-variants** (`tv()`) for component variants.

- All colors and spacing come from the Tailwind config (`tailwind.config.ts`), which is populated from the design token export (see TODO #04). **Never hardcode hex values or pixel numbers.**
- For truly dynamic values (e.g. `{ width: progress * 100 }`) use inline styles; for everything else use className.
- Keep `tv()` variant definitions co-located with their component.

```tsx
// Good
import { tv } from 'tailwind-variants'

const button = tv({
  base: 'rounded-full px-6 py-3 items-center',
  variants: {
    intent: {
      primary: 'bg-accent',
      ghost: 'border border-accent bg-transparent',
    },
  },
})

export function Button({ intent, label, onPress }: Props) {
  return (
    <Pressable className={button({ intent })} onPress={onPress}>
      <Text>{label}</Text>
    </Pressable>
  )
}

// Bad — hardcoded color, no variant system
<Pressable style={{ backgroundColor: '#C4694F' }}>
```

<!-- TODO #05: confirm NativeWind setup and tailwind.config.ts location -->

---

## State Management

<!-- TODO #05: fill in after scaffold -->

General rules (library-agnostic):
- Server state (API data) lives in TanStack Query — never replicate it into local state.
- Client state that needs to be shared across screens goes in the global store (Zustand).
- Component-local UI state (modal open, input focus) stays in `useState` — don't hoist unnecessarily.

---

## No useEffect for Derived State

Derive synchronously or use `useMemo`. `useEffect` + `setState` for derived values causes an extra render and is always avoidable.

```tsx
// Bad
const [fullName, setFullName] = useState('')
useEffect(() => {
  setFullName(`${first} ${last}`)
}, [first, last])

// Good
const fullName = `${first} ${last}`
// or, if expensive:
const fullName = useMemo(() => `${first} ${last}`, [first, last])
```

---

## Navigation

<!-- TODO #05: fill in typed navigation params pattern after scaffold -->

- Typed navigation params always — no untyped `useNavigation()` calls.
- No prop-drilling navigation props past 2 levels — use the navigation hook or store.

---

## Running the Project

<!-- TODO #05: fill in after scaffold -->

```bash
# placeholder — update when frontend is scaffolded
pnpm expo start
pnpm expo run:ios
pnpm expo run:android
```
