---
name: writing-react-effects
description: Writes React components without unnecessary useEffect. Use when creating/reviewing React components, refactoring effects, or when code uses useEffect to transform data or handle events.
disable-model-invocation: false
---

# Writing React Effects Skill

Guides writing React components that avoid unnecessary `useEffect` calls.

## Core Principle

> Effects are an escape hatch for synchronizing with **external systems** (network, DOM, third-party widgets). If there's no external system, you don't need an Effect.

## Decision Flowchart

When you see or write `useEffect`, ask:

```
Is this synchronizing with an EXTERNAL system?
├─ YES → useEffect is appropriate
│   Examples: WebSocket, browser API subscription, third-party library
│
└─ NO → Don't use useEffect. Use alternatives:
    │
    ├─ Transforming data for render?
    │   → Calculate during render (inline or useMemo)
    │
    ├─ Handling user event?
    │   → Move logic to event handler
    │
    ├─ Expensive calculation?
    │   → useMemo (not useEffect + setState)
    │
    ├─ Resetting ALL state when prop changes?
    │   → Pass different `key` to component
    │
    ├─ Adjusting SOME state when prop changes?
    │   → Calculate during render or rethink data model
    │
    ├─ Subscribing to external store?
    │   → useSyncExternalStore
    │
    └─ Fetching data?
        → Framework data fetching or custom hook with cleanup
```

## Anti-Patterns to Detect and Fix

| Anti-Pattern                                  | Problem                                                        | Alternative                                |
| --------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------ |
| `useEffect` + `setState` from props/state     | Causes extra re-render                                         | Compute during render                      |
| `useEffect` to filter/sort/transform data     | Unnecessary effect cycle                                       | Derive inline or `useMemo`                 |
| `useEffect` for click/submit handlers         | Loses event context                                            | Event handler                              |
| `useEffect` to notify parent on state change  | Breaks unidirectional data flow                                | Call parent callback in same event handler |
| `useEffect` with empty deps for one-time init | Runs twice in dev (Strict Mode); conflates app init with mount | Module-level code or `didInit` ref flag    |
| `useEffect` for browser subscriptions         | Error-prone manual cleanup                                     | `useSyncExternalStore`                     |
| `useEffect` + `setState` for derived state    | Double render, stale intermediate state                        | Compute value directly during render       |

## When useEffect IS Appropriate

- Syncing with external systems (WebSocket connections, third-party widgets, browser APIs)
- Setting up and cleaning up subscriptions
- Fetching data based on current props (always include cleanup to handle race conditions)
- Measuring or imperatively mutating DOM elements after render
- Integrating with non-React code (jQuery plugins, analytics SDKs, etc.)

## Common Refactoring Patterns

### Derived state → compute during render

```tsx
// ❌ Bad
const [filtered, setFiltered] = useState([]);
useEffect(() => {
  setFiltered(items.filter((i) => i.active));
}, [items]);

// ✅ Good
const filtered = items.filter((i) => i.active);
// or with useMemo for expensive operations
const filtered = useMemo(() => items.filter((i) => i.active), [items]);
```

### Notify parent → call in event handler

```tsx
// ❌ Bad
useEffect(() => {
  onSelect(selectedId);
}, [selectedId]);

// ✅ Good
function handleClick(id) {
  setSelectedId(id);
  onSelect(id);
}
```

### Reset state on prop change → key prop

```tsx
// ❌ Bad
useEffect(() => {
  setComment("");
}, [userId]);

// ✅ Good — key remounts the component, resetting all state
<ProfileForm key={userId} userId={userId} />;
```

### Data fetching → custom hook with cleanup

```tsx
// ❌ Bad — no cleanup, race conditions possible
useEffect(() => {
  fetch(`/api/user/${id}`)
    .then((r) => r.json())
    .then(setUser);
}, [id]);

// ✅ Good — cleanup prevents stale responses
useEffect(() => {
  let cancelled = false;
  fetch(`/api/user/${id}`)
    .then((r) => r.json())
    .then((data) => {
      if (!cancelled) setUser(data);
    });
  return () => {
    cancelled = true;
  };
}, [id]);

// ✅ Even better — use a data-fetching library (React Query, SWR, TanStack Query)
const { data: user } = useQuery({
  queryKey: ["user", id],
  queryFn: () => fetchUser(id),
});
```

## Instructions for Claude

When this skill is invoked:

1. **Identify every `useEffect` call** in the provided code
2. **Apply the decision flowchart** to each effect individually
3. **Flag anti-patterns** from the table above with a clear explanation of the problem
4. **Provide refactored code** using the appropriate alternative for each case
5. **Leave legitimate effects untouched** — only remove effects that don't belong
6. **When writing new components**, never reach for `useEffect` unless the flowchart confirms it's appropriate

Prioritize correctness over cleverness. A derived value computed inline is always clearer than an effect that syncs it into state.
