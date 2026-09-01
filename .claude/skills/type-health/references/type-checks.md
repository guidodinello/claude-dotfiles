# Type Health Checks

> **Purpose**: the mechanical half of `/type-health` — every grep, config
> check, and classification rule. The reasoning behind each one lives in
> [`type-philosophy.md`](type-philosophy.md).
>
> **Who reads this**: Step 1 (scan) and Step 1b (checker config) run these
> commands verbatim; the Step 2 classify agent uses the classification rules
> below alongside the philosophy doc.

**Never touch generated files** — skip `*.gen.ts`, `*.generated.*`,
`routeTree.gen.ts`, `alembic/versions/`, and `node_modules/`.

## Which heuristics this file can actually find

Not every heuristic is greppable, and pretending otherwise wastes a run.

| | Heuristics | How they surface |
|---|---|---|
| **Scanned** | H2, H3, H7c, H7d, H7e, H8, H9, H10, H11 | a grep in §1–2 targets them directly |
| **Judgment-only** | H1, H4, H5, H6, H7a, H7b | no grep targets them; they are for *classifying* what the other scans return and for reading a file by hand |

"Judgment-only" means no scan is *aimed* at the heuristic — not that a hit can
never be classified under it. H7b, for instance, has no grep but is measured by
the `exactOptionalPropertyTypes` check in §3, and H6 surfaces only as a FIX
bullet in §4 once some other scan has put the line in front of you.

H4 is the notable gap: there is no scan for a `match`/`switch` lacking
`assert_never`/`never`, which is the actual H4 failure mode. The string-literal
grep in §1 is a weak proxy at best — it finds the union, not the missing
exhaustiveness check. Verify H4 by hand when a union type shows up in a finding.

The judgment-only heuristics are why the classify step reads
[`type-philosophy.md`](type-philosophy.md) and not just this file.

---

## 1. Source scan — Python

Run from the repo root.

```bash
# Bare Any and dict[str, Any] (H3, H7d)
grep -rn ": Any\|-> Any\|\[Any\]\|dict\[str, Any\]" backend/src scripts --include="*.py" | sort

# Untyped container generics: bare list/dict/set/tuple annotations (H3).
# Anchored to an annotation position — the unanchored version matched only
# docstring prose ("pairs: list of (index, id)") and calls (`dict(counts)`),
# zero real annotations, on its first run.
grep -rnE "^\s*[a-z_]+: (list|dict|set|tuple)( *[=)]| *$)" backend/src scripts --include="*.py" | sort

# Public functions missing return annotations (H3)
grep -rnE "^(async )?def [a-z_]+\(.*\):$" backend/src scripts --include="*.py" | grep -v "def _" | sort

# String-literal comparisons that suggest a missing Literal/enum (H3).
# Not an H4 scan: it surfaces the union, never the missing exhaustiveness check.
grep -rnE "== ['\"][a-z_]+['\"]|in \(['\"]" backend/src --include="*.py" | sort

# Empty-string / -1 used as an "absent" sentinel instead of None (H7e)
# `if cred else` was removed — it still matches `users.py`'s
# `cred.identifier if cred else None`, but that instance is already fixed
# (`device_id` is `str | None` now), so every hit it produces is a false
# positive on the correct pattern.
grep -rnE ': str = ""|str = ""\)|else ""|-1\)? *(#.*absent|# no |# none)' backend/src --include="*.py" | sort

# Escape hatches — unverified claims the checker could not prove (H8)
grep -rn "cast(" backend/src scripts --include="*.py" | sort          # typing.cast, not sqlalchemy.cast
grep -rnE "# (type|pyright): ignore" backend/src scripts --include="*.py" | sort
grep -rnE "assert .* is not None" backend/src scripts --include="*.py" | sort
grep -rnE "\.one\(\)|\.scalar_one\(\)" backend/src scripts --include="*.py" | sort

# Mutable default arguments and in-place mutation of caller data (H9)
grep -rnE "def .*=\s*(\[\]|\{\}|set\(\))" backend/src scripts --include="*.py" | sort
# `.append`/`.extend` are deliberately excluded — building a local accumulator is
# idiomatic and drowns the signal. In-place reorder/replace is the real smell.
grep -rnE "^\s*[a-z_]+\.(sort|update|clear|reverse)\(" backend/src scripts --include="*.py" | sort

# Unbounded numerics on names that denote a bounded domain (H10).
# A bare `: float` scan returns 300+ hits and is useless — filter by field name.
grep -rnE ": (float|int)( |$|\)|,|\|)" backend/src scripts --include="*.py" \
  | grep -v "Field(" \
  | grep -iE "(score|distance|similarity|ratio|weight|threshold|confidence|probab|percent|norm|alpha|decay|ema)\s*:" \
  | sort

# Bounds that live in prose instead of in the type — the strongest H10 signal.
# Keep this narrow: "range"/"between" alone match hundreds of unrelated lines.
grep -rnE "\b(clamp|clamped|clamps)\b|512-dim|length 512|\[0, ?1\]|unit-normali" \
  backend/src scripts --include="*.py" | sort

# Vector/embedding shapes with no declared length (H10)
grep -rn "list\[float\]" backend/src scripts --include="*.py" | sort

# Validation-skipping construction and sanctioned-cast leakage (H11)
grep -rnE "model_construct\(|validate_assignment=False" backend/src scripts --include="*.py" | sort
grep -rnE "NewType\(" backend/src scripts --include="*.py" | sort
```

For the `cast(` hit list, confirm the file imports `cast` from `typing` and not
from `sqlalchemy` before classifying — they are unrelated.

## 2. Source scan — TypeScript

```bash
# any annotations (H3)
grep -rn ": any\|<any>\|any\[\]" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | sort

# as casts — especially `as unknown` chains (H2, H7c).
# The comment/import-type filters are load-bearing: a bare " as " scan returns
# 179 hits here (English prose in comments — "treated as an equivalent
# success" — plus `as const` and `import type * as X`); filtered, 65.
# Re-measure rather than trusting these numbers; they move with the tree.
grep -rn " as " frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | grep -v "as const" \
  | grep -vE ":\s*(\*|//|/\*)" | grep -v "import type" | sort

# filter(Boolean) followed by a cast — should be a type predicate.
# Require the cast: bare `.filter(Boolean).length` is a count, not a claim.
grep -rnE "filter\(Boolean\)[^.]*\bas\b" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | sort

# Untyped API calls bypassing the typed helpers (H2)
grep -rn "privateApi\.\(post\|put\|patch\|delete\)\|r\.data as" frontend/web/src \
  --include="*.ts" --include="*.tsx" | grep -vE "\.gen\.|\.generated\." | sort

# Route search params cast without a schema (H2)
grep -rn "search\.[a-zA-Z]* as " frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | sort

# Empty-string fallback that may be masking a missing-value case (H7e)
grep -rn "?? ''\|?? \"\"" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | sort

# Escape hatches (H8)
grep -rnE "[A-Za-z0-9_\)\]]![.\),;]" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -vE "\.gen\.|\.generated\." | sort
grep -rnE "@ts-(ignore|expect-error)" frontend/web/src | sort

# Mutation of a shared/exported object or a parameter (H9)
grep -rnE "^\s*[a-z][A-Za-z0-9_]*\.(sort|push|splice|reverse)\(" frontend/web/src \
  --include="*.ts" --include="*.tsx" | grep -vE "\.gen\.|\.generated\." | sort

# Unconstrained numeric / array schemas where a bound exists (H10)
# -P, not -E — the negative lookahead needs PCRE, and the two flags conflict
grep -rnP "z\.number\(\)(?!\.(min|max|int|positive|nonnegative))" frontend/web/src \
  --include="*.ts" --include="*.tsx" | grep -vE "\.gen\.|\.generated\." | sort
grep -rnE "z\.array\(" frontend/web/src --include="*.ts" --include="*.tsx" \
  | grep -v "length(" | grep -vE "\.gen\.|\.generated\." | sort

# Brand casts outside the module that owns the parse function (H11)
grep -rnE " as [A-Z][A-Za-z0-9]*(Id|Token|Email|Score)\b" frontend/web/src \
  --include="*.ts" --include="*.tsx" | grep -vE "\.gen\.|\.generated\." | sort
```

There is deliberately **no "known hotspots" list here.** The previous one named
three (`r.data as unknown` in `items.ts`/`users.ts`/`interactions.ts`, the
`store/flags.ts` hard cast, untyped search-param casts) and by the skill's first
run all three had been fixed. A stale hotspot list is worse than none: it invites
confirming a finding that no longer exists. Let the greps find what is there.

---

## 3. Checker-configuration audit

The scans above audit the code. This audits the *checker* — a missing strictness
flag silently exempts the whole codebase from a bug class, and no grep over
source files will ever reveal it.

Read `backend/pyproject.toml` `[tool.pyright]` and
`frontend/web/tsconfig.app.json`, then compare against the table below.

### Recommended flags

| Flag | Where | Catches | Heuristic |
|------|-------|---------|-----------|
| `typeCheckingMode = "strict"` | pyright | the baseline | H3 |
| `reportUnnecessaryTypeIgnoreComment` | pyright (off even in strict) | dead suppressions that hide nothing | H8 |
| `strict: true` | tsconfig | the baseline | H3 |
| `noUncheckedIndexedAccess` | tsconfig | `arr[i]` / `rec[k]` returning `T` when the index may not exist — Rust's bounds-checking made static | H8 |
| `exactOptionalPropertyTypes` | tsconfig | `{ x: undefined }` silently satisfying `{ x?: T }` | H7b |
| `noFallthroughCasesInSwitch` | tsconfig | missing `break` | H4 |
| `noImplicitOverride` / `reportImplicitOverride` | both | accidental override of a base method | — |

Also check pyright's `exclude` list, not just its flags — an excluded directory
is exempt from *every* rule above. `src/fitted_backend/ml` is currently
excluded, which is where the range-bearing floats and embedding vectors live
(H10's strongest targets). Report the exclusion as its own finding: Pydantic
`Field` constraints still validate there at runtime, but no static rule applies.

### Measure before recommending

Never report a flag as a finding on reputation alone — both TS flags below have
a reputation for being unbearable on existing codebases, and on this codebase
they are not. Run each and report the **actual** count:

```bash
# TypeScript — one run per candidate flag
cd frontend/web
npx tsc -p tsconfig.app.json --noEmit --noUncheckedIndexedAccess 2>&1 | grep -c "error TS"
npx tsc -p tsconfig.app.json --noEmit --exactOptionalPropertyTypes 2>&1 | grep -c "error TS"

# Also break down where the errors land — src/ vs src/__tests__/ changes the verdict
npx tsc -p tsconfig.app.json --noEmit --noUncheckedIndexedAccess 2>&1 \
  | grep "error TS" | sed 's/(.*//' | sort | uniq -c | sort -rn
```

Pyright has no equivalent one-shot CLI override for report flags, so the
setting must be added to `[tool.pyright]` in `backend/pyproject.toml` — a
tracked file. Run the edit, the measurement and the restore as **one command**,
so an error or an interrupted run can't leave the file modified:

```bash
cd backend && cp pyproject.toml /tmp/pyproject.bak && \
  uv run python -c "
import pathlib
p = pathlib.Path('pyproject.toml')
p.write_text(p.read_text().replace(
    '[tool.pyright]', '[tool.pyright]\nreportUnnecessaryTypeIgnoreComment = \"error\"'))
" && uv run pyright 2>&1 | grep -E "error|informations"; cp /tmp/pyproject.bak pyproject.toml
```

Grep for the count — do **not** pipe to `tail`. Pyright prints a two-line
version-upgrade warning *after* its summary, so `tail -3` shows the warning and
swallows the error count. (This bit both the skill's author and its first run.)

Then confirm the restore landed — from the **repo root**, not from `backend/`,
or the path silently matches nothing:

```bash
cd .. && git status --porcelain backend/pyproject.toml   # must print nothing
```

Report each missing flag as its own finding with the measured count, always
categorized **INVESTIGATE** — turning a flag on changes the CI contract for
everyone and is a decision for a human, never something this skill applies
silently.

---

## 4. Classification rules

Classify every hit into one of three categories. Read ~20 lines of context
around the line in the actual file first — never classify from the grep string.

### FIX — the type can be tightened without changing behavior

- `dict[str, Any]` where the code below clearly knows the shape → Pydantic model (H7d)
- `Any` that can be a specific type, `TypedDict`, or `Literal` union (H3)
- Bare container generics (`list` → `list[str]`)
- Missing annotations on public functions
- String literal sets checked in multiple places → `Literal` / enum / `as const` object (H2, H4)
- `as unknown as T` or `r.data as unknown` → Zod schema + typed `apiGet`/`privateApiGet` helper (H7c)
- Hard cast without runtime validation (`data as { flags: ... }`) → `.safeParse()` or a type guard
- `filter(Boolean) as T[]` → type predicate `.filter((x): x is T => x != null)`
- Untyped function parameters (TS infers `any` for params — always annotate)
- Unnecessary explicit return type on an internal function where inference is narrower
- Route search-param `as string | undefined` → `z.string().optional().parse()` or a search-param schema
- Single-value validation done by hand → `pydantic.TypeAdapter`
- Empty string / `-1` / `0` manufactured as an "absent" sentinel → `T | None` / `.nullable()` at **both** the producing and consuming boundary (H7e)
- Bare tuple with positional meaning → `NamedTuple`
- Primitive ID or unit-bearing number crossing a boundary → `NewType` / brand (boundaries only; don't overuse internally) (H6)
- Boolean flag paired with nullable data → discriminated union (H1, H7a)
- Inline `useMutation`/`useQuery` duplicated across components → reusable hook
- `cast(T, x)` immediately after a check the checker *can* follow → delete the cast (H8)
- Bare `# type: ignore` where the error code is known → scope it to `# type: ignore[code]` (H8)
- A **dead** suppression — scoped or bare — that `reportUnnecessaryTypeIgnoreComment` reports as unnecessary → delete it. Deleting a suppression that suppresses nothing is a no-op at runtime and cannot break a build; it only needs the measurement from §3 to identify it. (Check first whether a second checker the project runs still needs it — if pyright is the only checker, it doesn't.) (H8)
- `assert x is not None` guarding production logic → `if x is None: raise ...` (asserts vanish under `-O`) (H8)
- Mutable default argument (`def f(xs: list = [])`) → `None` sentinel + local construction (H9)
- Parameter typed `list[T]` / `T[]` but never mutated → `Sequence[T]` / `readonly T[]` (H9)
- A bound stated only in a docstring/comment, or enforced only by a `max()`/`min()` clamp in the body → tighten it **statically** where the language allows (`int` → `Literal[...]`, a stringly-typed code → an enum). If the only way to express the bound is a *validating* constraint — `Field(ge=…, le=…)`, `z.number().min().max()` — it is INVESTIGATE, not FIX; see below (H10)
- A sanctioned brand cast (`as UserId`) sitting outside the module that owns the parse function → route it through that parse function (H11)

### LEGITIMATE — the loose type is correct

- `Any` in genuinely dynamic code (e.g. `**kwargs` passthrough to a library)
- `as` for DOM narrowing (`e.target as HTMLInputElement`)
- Third-party library types that can't be tightened without stubs
- `dict[str, Any]` for truly open-ended payloads (raw webhook body logged, never accessed by key)
- `cast()` / scoped `ignore` compensating for wrong or missing library stubs — **provided a comment says so**. An uncommented escape hatch is never LEGITIMATE; at minimum the finding is "add the justification". (H8)
- `.one()` where a DB uniqueness constraint guarantees the row
- Mutation of a locally-constructed collection that never escapes the function (H9)
- A numeric whose "range" is a tunable business rule rather than a property of the value (a configurable threshold), or an intermediate arithmetic result where out-of-range is a legitimate transient (H10)
- `model_construct` on a trusted internal path where validation was already performed upstream — provided a comment says so (H11)

### INVESTIGATE — needs a design decision or a multi-file refactor

- Anything changing a shared signature or introducing a new schema module
- Every checker-configuration finding from section 3
- Migrating many bare `list[float]` signatures onto a constrained alias — a multi-file refactor, and the alias itself carries a validating constraint (see the next bullet) (H10)
- **Adding a validating constraint at an IO boundary is never a FIX.** This covers Zod (`z.number()` → `.min().max()`, `z.array()` → `.length(n)`) *and* Pydantic (`Annotated[float, Field(ge=…, le=…)]`, `Field(min_length=n)`) alike — the language is not the axis, execution is. Unlike a purely static annotation, these run: a payload the app previously accepted now throws at `.parse()` / `model_validate()`. Trace the value's full provenance before proposing it, and hand the decision to a human.

  > A real near-miss from this skill's first run: `RecommendedItemSchema.score` looks like a textbook `[0, 1]` case — `ConceptScoreSchema.score` in the *same file* is already `.min(0).max(1)`. But `freshness.py` multiplies scores by `max_boost = 1.5`, so recommendation scores legitimately exceed 1 and the "fix" would have failed `.parse()` on every feed response. Only following the call chain three modules deep catches it. Also ask whether the value is even read — an unread field gains a rejection path and nothing else.
  >
  > The Pydantic half is not hypothetical either: the same run tightened `TasteVector` to `Field(min_length=512, max_length=512)`. `ML_DIMENSION` is a settable env var, so on any deployment where it is not 512 that annotation turns `POST /onboarding/answers` into a 500. The constraint is defensible — the DB columns are `Vector(512)` — but that is a judgment call about which source of truth wins, which is exactly what INVESTIGATE is for.
- Anything that would require deciding *where parse functions live* or *whether raw constructors become private* — H11's broad form awaits that project decision; only sanctioned-cast leakage is FIX
- A product invariant brushed by a scan (cooldown windows, per-week notification caps, idempotency keys): note "invariant — belongs in property-based tests, see `/write-tests`" and move on. These are not type findings
- Anything the philosophy doc lists under "Concepts we document but do not
  check" — those are background reading, not findings; do not open them at all

Be conservative — when in doubt, mark INVESTIGATE, not FIX.

---

## 5. Quick audit checklist

When reviewing a single file by hand, scan in this order:

1. ❌ `Any` / `any` annotations → H3
2. ❌ `as SomeType` on API responses → H2, H7c
3. ❌ `as unknown as SomeType` → H7c (immediate fix)
4. ❌ `dict[str, Any]` / `Record<string, any>` for known shapes → H7d
5. ❌ `cast(...)`, bare `# type: ignore`, `x!`, `@ts-expect-error` → H8
6. ❌ Boolean flags paired with nullable data → H7a, H1
7. ❌ Switch/match without `never` / `assert_never` → H4
8. ❌ Pydantic models or Zod types deep in business logic → H5
9. ❌ `string`/`int` IDs or unit-bearing numbers crossing domains → H6
10. ❌ Same union value checked in >3 places (should have been parsed at the boundary) → H2
11. ❌ Empty string / `-1` / `0` meaning "absent" instead of `None`/`null` → H7e
12. ❌ Mutable default args; `list`/`T[]` params that are never mutated → H9
13. ❌ A bound in a docstring or a `max()`/`min()` clamp, but not in the type → H10
14. ❌ `list[float]` / `z.array()` for a fixed-length vector → H10
15. ❌ A brand cast or `model_construct` outside the module that owns parsing → H11
