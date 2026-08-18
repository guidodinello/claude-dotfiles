---
paths:
  - "**/*.js"
  - "**/*.mjs"
  - "**/*.cjs"
  - "**/*.jsx"
  - "**/*.ts"
  - "**/*.tsx"
  - "**/package.json"
  - "**/tsconfig*.json"
---

<!-- Code examples and table rows can't be rewrapped without breaking them;
     prose is held to 80 columns. This directive travels with the file so it
     lints clean in any repo that vendors it. Claude Code strips block HTML
     comments before injection, so this costs no context. -->
<!-- markdownlint-configure-file {
  "MD013": { "code_blocks": false, "tables": false }
} -->

# JavaScript & TypeScript — Agent Code Guidelines

General-purpose guidelines for JavaScript/TypeScript projects where AI agents
assist with development. As a path-scoped rule it self-loads on `.js` /
`.ts` / `.jsx` / `.tsx` / `package.json` / `tsconfig*.json` — never copy it
into a project's `CLAUDE.md`. Adapt the project-specific sections at the
bottom when adopting it in a new project.

---

## Philosophy

- **Explicit is better than implicit** — no magic, no hidden coercion, no
  surprising mutation. If a function does something non-obvious, a name or
  comment should say so.
- **Simple is better than clever** — the right solution is usually the least
  code that correctly solves the problem, not the most flexible abstraction.
- **Readability counts** — code is read far more often than it is written.
  Optimise for the reader, not for the fewest keystrokes.
- **Errors should never pass silently** — fail loudly and early. Don't swallow
  a rejection or return `undefined` where an error is the right answer.
- **Most formatting is not a judgment call here** — ESLint/Prettier or Biome
  own layout, quote style, and semicolons. This file covers what tooling
  can't enforce: module boundaries, error handling, dependency discipline.

---

## Software engineering principles

### YAGNI — You Aren't Gonna Need It

Don't add props, config options, or abstraction layers for hypothetical future
requirements. Build what the task actually needs. If the requirement arrives
later, add it then.

```ts
// Bad — parameterised "for future flexibility"
function train(optimizer = "adam", scheduler?: string, warmupSteps = 0, gradClip?: number) {}

// Good — add parameters when there's an actual reason to vary them
function train(lr = 3e-4) {}
```

### DRY — Don't Repeat Yourself (but don't over-apply it)

Duplicate code is a maintenance hazard. Extract shared logic — but only once
you see the same thing repeated at least three times and are confident the
repetition isn't coincidental. Premature abstraction is worse than
duplication.

### SSOT — Single Source of Truth

Every piece of knowledge — a constant, a shape, a business rule — should have
exactly one authoritative definition. Everything else derives from or
references that definition; nothing duplicates it.

```ts
// Bad — the valid states are defined twice; the union and the array can drift
const VALID_STATUSES = ["pending", "active", "closed"];
type Status = "pending" | "active" | "closed";

function isValid(s: string): s is Status {
  return VALID_STATUSES.includes(s); // duplicates knowledge already in Status
}

// Good — one definition; the type and the runtime check both derive from it
const STATUS_VALUES = ["pending", "active", "closed"] as const;
type Status = (typeof STATUS_VALUES)[number];
const STATUSES: ReadonlySet<string> = new Set(STATUS_VALUES);

function isValid(s: string): s is Status {
  return STATUSES.has(s); // no cast — Set<string>.has(string) needs none
}
```

The test: if renaming or removing one thing requires finding and updating a
second place, you have two sources of truth.

### KISS — Keep It Simple

Prefer a plain function over a class. Prefer a class over a framework. Each
layer of indirection has a cost; make sure it earns it.

Jack Diederich's rule (originally aimed at Python, but it travels): *if you
can't explain what the class does without using the word "manager",
"handler", or "helper" — it probably shouldn't be a class.*

### Single responsibility

Functions and components should do one thing. If a function's name needs
"and", split it. If a component has state that isn't related to what it
renders, split it.

The naming test: if you can't find a single, precise name that covers
everything a function does, it's doing too much.

```ts
// Bad — the name has to say "and", revealing two responsibilities
function validateAndSaveUser(user: User): void {}

// Good — each function has one job and a name that fits it exactly
function validateUser(user: User): void {}
function saveUser(user: User): void {}
```

### Locality of Behavior

Code that changes together should live together. A reader should be able to
understand a behavior by reading one place, not by chasing references across
files.

- Define constants near the code that uses them — not in a shared
  `constants.ts` that becomes a catch-all.
- Keep a validator next to the shape it validates.
- Keep a helper function adjacent to its only caller rather than hoisting it
  to a `utils/` module it doesn't belong in.
- Component-local state and styles belong next to the component, not
  scattered across a shared store or stylesheet.

The test: if understanding one behavior requires opening more than two files,
the behavior has too much distance.

### Fail fast

Validate inputs at the boundary (user input, API responses, `JSON.parse`,
`localStorage`). Inside the system, trust your own invariants and let
unexpected states throw immediately rather than propagating silently.

```ts
// Bad — silently returns a wrong result
function divide(a: number, b: number): number {
  if (b === 0) return 0;
  return a / b;
}

// Good — caller learns about the problem immediately
function divide(a: number, b: number): number {
  if (b === 0) throw new Error(`divide: b must be non-zero, got ${b}`);
  return a / b;
}
```

---

## Running the project

```bash
pnpm install          # install pinned dependencies from the lockfile
pnpm run lint             # lint (must be clean before committing)
pnpm run lint -- --fix    # auto-fix what the linter can
pnpm run build         # type-check + build
pnpm run test          # run test suite (must be green before committing)
```

Use whichever package manager the lockfile names (`pnpm-lock.yaml`,
`package-lock.json`, `yarn.lock`) — never mix lockfiles in one project.

---

## Modules & imports

Default to ESM (`"type": "module"` in `package.json`, `import`/`export`).
Reach for CommonJS only when a dependency or runtime forces it.

**Use the `node:` prefix for Node builtins** in server-side code —
`import { readFile } from "node:fs/promises"`, not `"fs"`. It makes the
builtin explicit and unambiguous to a reader, and is required for a few
newer builtins that have no unprefixed form at all.

```ts
// Good
import { readFile } from "node:fs/promises";

// Bad — reads as if it might resolve to a userland package
import { readFile } from "fs";
```

Don't import from a package's internal paths — only its declared
`exports` map is the public surface. A deep import breaks on the package's
next minor release with no warning from semver.

```ts
// Bad — reaches past the package's public API
import debounce from "lodash/debounce.js";

// Good — the declared entry point
import { debounce } from "lodash-es";
```

No wildcard re-export barrels (`export * from "./thing"`) in a package
that's meant to be tree-shaken. A bundler *can* shake through a barrel
when the package sets `"sideEffects": false` and every re-export is clean
— but that's a fragile precondition most packages don't meet, and even
when they do, mixed inline-export/re-export barrels have open tree-shaking
gaps in current bundlers. Treat "barrels are tree-shaken" as something to
verify for a specific package, not something to assume.

---

## Types (TypeScript)

Turn on `strict: true` in `tsconfig.json`. **Never use `any`** — use
`unknown` and narrow it. **Never use the non-null assertion (`!`)** — it's
a claim, not a check, and the whole point of `strict` is not needing to make
that claim silently.

```ts
// Bad
function parse(input: any): any {
  return JSON.parse(input);
}

// Good — unknown forces the caller to narrow before using the value
function parse(input: string): unknown {
  return JSON.parse(input);
}
```

Make `switch` statements over a union exhaustive with a `never` check, so
adding a new union member is a compile error everywhere it isn't handled:

```ts
function label(status: Status): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "active":
      return "Active";
    case "closed":
      return "Closed";
    default: {
      const _exhaustive: never = status;
      throw new Error(`unhandled status: ${_exhaustive}`);
    }
  }
}
```

`as` casts a value without checking it — it's a compile-time claim, not a
runtime guarantee. Prefer a type guard or a parsing function (Zod, `io-ts`,
a hand-written narrowing function) at any boundary where the data didn't
originate from TypeScript itself (an API response, `JSON.parse`, form input).

> **Boundary**: this section covers the cheap universal wins. Type-system
> *design* — making illegal states unrepresentable, parse-don't-validate,
> branded types — goes deeper than a general-purpose rule should. If the
> project has a `/type-health` skill, its heuristics are the fuller version
> of this section; consult it before re-deriving type-design judgment calls
> here.

---

## Equality, coercion, and absence

**Always use `===`/`!==`.** `==` performs implicit coercion whose rules are
themselves a common source of bugs (`"" == 0` is `true`, `null == undefined`
is `true` but `null == 0` is `false`).

Use `??` (nullish coalescing) for a default that should apply only to
`null`/`undefined`, not `||`, which also overrides `0`, `""`, and `false`:

```ts
// Bad — a legitimate 0 quantity gets replaced by the default
const qty = input.quantity || 10;

// Good — only null/undefined triggers the default
const qty = input.quantity ?? 10;
```

Use optional chaining (`?.`) instead of a chain of manual `&&` guards. Pick
one absence value per codebase — `undefined` for "not provided", `null` for
"explicitly empty" — and use it consistently; mixing both without a reason is
a code smell.

---

## Error handling

Throw `Error` instances, never bare strings or plain objects — only `Error`
carries a stack trace.

```ts
// Bad — no stack trace, callers can't tell what type of failure this is
throw { message: "user not found" };

// Good
throw new Error("user not found");
```

Chain errors with the `cause` option instead of losing the original failure
when wrapping it:

```ts
try {
  await sendRequest();
} catch (err) {
  throw new Error("failed to notify downstream service", { cause: err });
}
```

Use `AggregateError` when reporting multiple failures from a fan-out (e.g.
`Promise.allSettled`), instead of surfacing only the first one.

**Identify an error by a stable `code`, never by matching `error.message`.**
Message text is not part of any API contract and can change between
versions of a dependency.

```ts
// Bad — breaks the moment the message wording changes upstream
if (err.message === "ECONNREFUSED") {}

// Good
if (err.code === "ECONNREFUSED") {}
```

Define a base error class per package so callers can catch your errors
specifically:

```ts
class AppError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = new.target.name;
  }
}

class NotFoundError extends AppError {}
```

---

## Async

**Every promise gets a rejection handler.** A floating promise silently
swallows its error — either `await` it, `.catch()` it, or hand it to
something that will.

```ts
// Bad — rejection is unobserved
sendAnalyticsEvent(event);

// Good
await sendAnalyticsEvent(event);
// or, when the caller must not block on it:
sendAnalyticsEvent(event).catch((err) => logger.error("analytics failed", { err }));
```

Use `Promise.all` for independent work run concurrently, not a sequential
`for` loop with `await` inside it — the loop serialises work that has no
reason to be serial:

```ts
// Bad — each request waits for the previous one to finish
for (const id of ids) {
  results.push(await fetchUser(id));
}

// Good — all requests run concurrently
const results = await Promise.all(ids.map(fetchUser));
```

Use `AbortController` to make a fetch or long-running operation cancellable
instead of leaving it to run to completion after the caller has moved on.

---

## Immutability and data shape

Default to `const`; reach for `let` only when a binding genuinely needs to be
reassigned. Avoid mutating a function's arguments — return a new value
instead, so callers can reason about a function from its signature alone.

```ts
// Bad — mutates the caller's array
function addItem(items: Item[], item: Item) {
  items.push(item);
}

// Good — caller decides whether to keep the old array
function withItem(items: Item[], item: Item): Item[] {
  return [...items, item];
}
```

Prefer plain data (object literals, discriminated unions) over classes for
values that are just data. Reach for a class only when behavior and state
are genuinely coupled.

---

## Code smells to avoid

These patterns are warning signs that the design needs rethinking:

- **`any` as an escape hatch** — every `any` is a hole in the type system
  that silently swallows real bugs at every call site it touches.

- **Boolean flags that select behaviour** — split into two functions
  instead:

  ```ts
  function process(data: Data, verbose = true) {} // Bad — two functions in a trenchcoat

  function process(data: Data) {} // Good
  function processVerbose(data: Data) {} // Good
  ```

- **`useEffect` for derived state** — a value computed from props or state
  belongs in render, not in an effect that sets state after the fact. See
  the `writing-react-effects` skill for the full treatment.

- **`JSON.parse` without validation at an IO boundary** — the result is
  typed `any` by TypeScript's own lib types; a typo in a field name becomes
  a silent `undefined` three call sites away instead of an error at the
  boundary.

- **`Array.prototype.sort`/`reverse`/`splice` on a value the caller still
  holds a reference to** — these mutate in place and silently corrupt
  whatever else was pointing at that array. Copy first (`[...arr].sort()`)
  unless the array is genuinely local and owned.

- **Default-export-only modules in a library** — a default export can't be
  auto-imported by name and re-exports awkwardly; prefer named exports for
  anything with more than one thing to export.

- **Deeply nested ternaries** — if a conditional expression needs more than
  one level of nesting to read, an `if`/`else` or a lookup table is clearer.

- **Classes with no shared state** — if every method could be a free
  function, it probably should be. (See: Jack Diederich, *Stop Writing
  Classes*.)

---

## Dependency discipline

Commit the lockfile. A dependency version that isn't pinned by a committed
lockfile is a version nobody actually tested against.

Before adding a dependency, weigh it against writing the ten lines yourself —
every dependency is a supply-chain surface, a bundle-size cost, and an
upgrade obligation that outlives the feature it was added for.

When overriding a dependency's version to force a security patch, pin an
explicit upper bound per override — pnpm's `pnpm.overrides` key accepts a
per-major `"pkg@range"` selector, but a bare top-level `overrides` key in
`package.json` silently ignores that selector syntax, and an unbounded
override floats clean past the major version you actually meant to pin.

---

## Node runtime

The rest of this file applies to any JS/TS codebase; this section applies
only when the code runs server-side under Node, not in a browser.

- Set `process.exitCode` and let the event loop drain naturally, instead of
  calling `process.exit()`, which kills in-flight I/O (unflushed logs,
  pending writes) immediately.
- Prefer streams (`fs.createReadStream`) over reading a whole file into
  memory (`fs.readFile`) when the file's size isn't bounded by the caller.
- Never call a synchronous fs function (`readFileSync`, `writeFileSync`) on
  a request-handling hot path — it blocks the entire event loop for every
  other in-flight request.
- Read environment variables (`process.env`) at one startup boundary into a
  typed config object, not scattered through the codebase — an unset env
  var should fail at startup, not three modules deep at first use.

---

## Tests

Every non-trivial module needs tests. Minimum coverage:

- **Happy path** — does the function return the right thing for normal
  input?
- **Edge cases** — empty arrays, zero, `null`/`undefined`, boundary values.
- **Invariants** — properties that must always hold (e.g. output shape,
  value bounds).

```bash
pnpm run test
```

Structure:

```text
src/
  thing.ts
  thing.test.ts       # co-located unit test, same directory as the source
```

---

## Linting

ESLint (flat config) or Biome as the single linter/formatter — don't run
both on the same files. Suggested flat-config baseline:

```js
// eslint.config.js
import js from "@eslint/js";
import ts from "typescript-eslint";

export default ts.config(js.configs.recommended, ...ts.configs.strict);
```

Run the lint/format script before every commit. Inline `// eslint-disable`
is a last resort — prefer an override entry scoped to the offending file,
with a comment explaining why.

---

## Project-specific notes

Replace this section when adapting these guidelines for a new project.

| Item | Value |
| ------ | ------- |
| Runtime | Browser (Vite) |
| Package manager | pnpm |
| Type checker | tsc |
| Test runner | Vitest |
| Linter/formatter | ESLint (flat config) |
