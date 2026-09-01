# Type Design Philosophy

> **Purpose**: the *why* behind every finding the `/type-health` skill reports.
> The mechanical patterns live in [`type-checks.md`](type-checks.md); this file
> is what lets a classifier make a judgment call on a finding that no grep can
> decide.
>
> **Who reads this**: the Step 2 classify agent (alongside `type-checks.md`),
> and any human deciding whether an `INVESTIGATE` finding is worth acting on.

The goal is to tighten types where it prevents real bugs, not to maximize
annotation count. A well-typed codebase should produce few findings.

## Lineage

Nothing here is original. The heuristics are imports from the ML/Haskell
tradition and from Rust, and it helps to know which idea came from where —
when a heuristic feels arbitrary, the source usually explains it.

| Heuristic | Origin |
|-----------|--------|
| H1 — illegal states unrepresentable | Wlaschin / F#-ML |
| H2 — parse, don't validate | Alexis King (Haskell) |
| H3 — precision hierarchy | general "make the type carry the invariant" |
| H4 — totality / exhaustiveness | `-Wincomplete-patterns`, Rust `match` |
| H5 — boundary vs. core | hexagonal architecture, functional core / imperative shell |
| H6 — branded types | Haskell `newtype`, Rust newtype pattern |
| H7a — boolean blindness | Haskell-community coinage |
| H8 — partial functions | Haskell partiality, Rust `.unwrap()` lint culture |
| H9 — immutability by default | Rust ownership |
| H10 — range and shape constraints | Ada/SPARK subtypes, the transferable half of dependent types |
| H11 — constructor discipline | ML module signatures / abstract types (OCaml, F#) |

---

## H1 — Make Illegal States Unrepresentable

**The idea.** A type that permits nonsensical combinations shifts the burden of
correctness from the compiler to runtime tests and memory. Every "wait, can
`paidAt` be `undefined` when `status` is `paid`?" question represents a class of
bugs the type system could have eliminated.

**Bad** — optional fields that should be mutually exclusive:

```ts
type Order = {
  id: string;
  status: string;
  paidAt?: Date;
  refundedAt?: Date;
  cancelReason?: string;
};
// { status: "pending", paidAt: new Date() } is valid — nonsense
```

```py
class Order(BaseModel):
    id: str
    status: str
    paid_at: datetime | None = None
    refunded_at: datetime | None = None
    cancel_reason: str | None = None
# Order(status="pending", paid_at=now()) is valid — same problem
```

Also flag boolean flags that gate which fields are meaningful:

```ts
type State = { isLoading: boolean; data?: Data; error?: Error };
// Four states, three of which are illegal: (loading=true, data=present)
```

**Good** — discriminated unions (sum types):

```ts
type Order =
  | { id: string; status: "pending" }
  | { id: string; status: "paid"; paidAt: Date }
  | { id: string; status: "cancelled"; cancelReason: string }
  | { id: string; status: "refunded"; paidAt: Date; refundedAt: Date };

type AsyncState<T> =
  | { tag: "idle" }
  | { tag: "loading" }
  | { tag: "success"; data: T }
  | { tag: "error"; error: Error };
```

```py
from typing import Literal, Union
from pydantic import BaseModel

class OrderPending(BaseModel):
    id: str
    status: Literal["pending"] = "pending"

class OrderPaid(BaseModel):
    id: str
    status: Literal["paid"] = "paid"
    paid_at: datetime

class OrderCancelled(BaseModel):
    id: str
    status: Literal["cancelled"] = "cancelled"
    cancel_reason: str

Order = Union[OrderPending, OrderPaid, OrderCancelled]
```

**Priority: High** — eliminates entire bug classes at compile time. Catches the
most subtle state-management bugs.

---

## H2 — Parse, Don't Validate

**The idea.** Validation that doesn't refine the type is information thrown
away. Every downstream re-check is a leak in the type system's proof — and a
site where a future edit can forget to check.

**Bad** — a check that verifies a constraint but returns the same unrefined type:

```ts
function validateEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
// Downstream: if (validateEmail(x)) { send(x) } — still string, could be invalid again
```

```py
def validate_non_empty(items: list) -> bool:
    return len(items) > 0
# Downstream: if validate_non_empty(items): first = items[0] — still can't prove it's safe
```

Also flag `JSON.parse(raw) as T` at API boundaries — a lie, since runtime data
may not match.

**Good** — functions that parse input into a refined, narrower type:

```ts
type NonEmptyArray<T> = [T, ...T[]];

function parseNonEmpty<T>(items: T[]): NonEmptyArray<T> {
  if (items.length === 0) throw new Error("Array is empty");
  return items as NonEmptyArray<T>;
}
```

```py
from typing import TypeVar, Annotated
from pydantic import TypeAdapter, Field

T = TypeVar("T")
NonEmptyList = Annotated[list[T], Field(min_length=1)]

adapter = TypeAdapter(NonEmptyList[T])

def parse_non_empty(items: list[T]) -> NonEmptyList[T]:
    return adapter.validate_python(items)
```

Zod at API boundaries:

```ts
const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  age: z.number().int().min(0).max(150),
});
type User = z.infer<typeof UserSchema>;

async function fetchUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  return UserSchema.parse(await res.json());
  // After this: user is guaranteed valid — no more checks needed
}
```

**Priority: High** — directly eliminates the most common source of runtime
crashes (assuming shape of untrusted data). Also removes redundant validation.

---

## H3 — Precision Hierarchy

**The idea.** Every step up the hierarchy gives the type checker more
information to catch mismatches. `Any` disables checking entirely; broad types
like `dict` admit valid-looking values that are wrong in context; strings can be
swapped between semantically distinct domains.

```py
# increasing precision
def process(item: Any) -> ...               # (0) type checker disabled
def process(item: dict) -> ...              # (1) bare dict
def process(item: dict[str, Any]) -> ...    # (2) typed values, unknown shape
def process(item: dict[str, str]) -> ...    # (3) tight values, generic container
def process(name: str) -> ...               # (4) string where a literal union fits
```

| Level | Python | TypeScript | Catches |
|-------|--------|-----------|---------|
| 0 — Any | `Any` | `any` | Nothing — checking disabled |
| 1 — Base | `object` | `unknown` | Forces refinement before use |
| 2 — Container | `dict[str, X]` | `Record<string, X>` | Key/value type mismatches |
| 3 — Shape | `BaseModel` / `TypedDict` | `interface` / `type` | Missing/extra fields |
| 4 — Literal | `Literal["a", "b"]` | `"a" \| "b"` | Wrong constant values |
| 5 — Constrained | `Annotated[str, Field(min_length=1)]` | `z.string().min(1)` | Invalid domain values |
| 6 — Branded | `NewType` | `Brand<T, K>` | ID cross-contamination |

**Priority: High** — `Any`/`any` suppression is the #1 source of undetected
regressions. Each level up catches a new bug class.

---

## H4 — Totality / Exhaustiveness

**The idea.** Adding a new variant to a union type is a cross-cutting change.
Without exhaustiveness checks, no compiler error tells you which functions need
updating — the bug manifests as a silent `undefined` return or a runtime
`KeyError`.

**Bad**:

```ts
function handleOrder(order: Order) {
  switch (order.status) {
    case "pending": return renderPending(order);
    case "paid": return renderPaid(order);
    // "cancelled" added — compiles fine, returns undefined
  }
}
```

```py
def handle_order(order: Order):
    match order.status:
        case "pending": return render_pending(order)
        case "paid": return render_paid(order)
        # "cancelled" added — silently falls through
```

**Good**:

```ts
function handleOrder(order: Order): string {
  switch (order.status) {
    case "pending": return renderPending(order);
    case "paid": return renderPaid(order);
    case "cancelled": return renderCancelled(order);
    case "refunded": return renderRefunded(order);
    default:
      const _exhaustive: never = order;
      return _exhaustive;
  }
}
```

```py
from typing import assert_never

def handle_order(order: Order) -> str:
    match order:
        case OrderPending(): return render_pending(order)
        case OrderPaid(): return render_paid(order)
        case OrderCancelled(): return render_cancelled(order)
        case _ as unreachable: assert_never(unreachable)
```

**Priority: High** — prevents silent regressions when domain types evolve.
Without this, adding enum variants is a landmine.

---

## H5 — Boundary vs. Core Distinction

**The idea.** "Type infection" — validated types carry runtime overhead and
coupling to serialization concerns (field aliases, validation contexts). If
every function takes a Pydantic model, you can't test business logic without
constructing a validated model, and you can't refactor the API schema without
touching core code. The reverse leak matters too: raw `dict[str, Any]` /
`unknown` should not survive past the boundary into core logic.

**Bad** — validated types deep in business logic:

```py
def calculate_discount(order: OrderPydanticModel) -> float:
    return order.total * 0.1  # coupled to Pydantic; testing needs a full model
```

```ts
function applyDiscount(user: z.infer<typeof UserSchema>): number {
  // internal function coupled to the HTTP boundary type
}
```

**Good** — parse at the edge, narrow types in the middle:

```py
@app.post("/discount")
def discount_endpoint(order: OrderPayload) -> DiscountResponse:
    core_order = OrderCore(total=order.total, items=[...])
    return DiscountResponse(amount=calculate_discount(core_order))

@dataclass(frozen=True)
class OrderCore:
    total: Decimal
    items: list[ItemCore]

def calculate_discount(order: OrderCore) -> float:
    return float(order.total) * 0.1
```

```ts
const handler = (req: Request) => {
  const input = OrderSchema.parse(req.body);
  const core: OrderCore = { total: input.total, items: input.items };
  return calculateDiscount(core);
};

interface OrderCore {
  total: number;
  items: ItemCore[];
}
```

**Priority: Medium** — less immediately crash-prone than missing validation, but
determines whether the codebase scales with complexity.

---

## H6 — Branded / Nominal Types

**The idea.** Structural typing treats `string` as `string` regardless of
semantic meaning. ID cross-contamination is a subtle bug: wrong record fetched,
wrong user charged. Brands catch these at compile time with zero runtime cost.

**Bad**:

```ts
function getUser(id: string): User { ... }
function getOrder(id: string): Order { ... }
getOrder(userId);                       // no error

function assign(userId: string, orderId: string): void { ... }
assign(orderId, userId);                // both string — swap compiles silently
```

**Good**:

```ts
type UserId = string & { __brand: "UserId" };
type OrderId = string & { __brand: "OrderId" };

function getUser(id: UserId): User { ... }
getUser("def456" as OrderId);   // Type error
```

```py
UserId = NewType("UserId", int)
OrderId = NewType("OrderId", int)

def get_user(id: UserId) -> User: ...
get_user(OrderId(1))            # Type error (pyright)
```

### Units of measure

The same mechanism, applied to quantities rather than identities. A bare
`price: int` does not say whether it holds cents or whole units, and the two
get mixed silently — a 100× error that no test catches unless someone wrote an
assertion about the exact number.

```ts
type Cents = number & { __unit: "Cents" };
type Dollars = number & { __unit: "Dollars" };
function formatPrice(amount: Cents): string { ... }
```

```py
Cents = NewType("Cents", int)
Millis = NewType("Millis", int)
```

Brand the unit at the boundary where the value is parsed, and unwrap only where
arithmetic happens.

**When NOT to use**: value types that are heavily computed (arithmetic breaks
brands — every operation needs an unwrap); types crossing many serialization
boundaries, where the brand is stripped and re-applied so often it stops
proving anything.

**Priority: Medium** — a narrow but costly bug class. High leverage in
auth/identity and money-handling code; low in display-only code.

---

## H7 — Null / Optional Hygiene

### H7a — Boolean Blindness

**The idea.** Booleans throw away information — `true` means "the condition was
met" but not *why*. Paired with a nullable value, they create four states of
which only two are valid, and the type system can't enforce the pairing.

**Bad**:

```ts
function getResult(): [boolean, Data | null] { ... }

type Response = { success: boolean; data?: Data; error?: Error };
// { success: true, error: new Error() } is valid — nonsense

sendEmail(user, true, false);  // what do these booleans mean?
```

**Good**:

```ts
type Result<T, E> =
  | { success: true; data: T }
  | { success: false; error: E };

type SendOptions = { urgent: boolean; html: boolean };
sendEmail(user, { urgent: true, html: false });
```

```py
class Success(BaseModel):
    success: Literal[True] = True
    data: Data

class Failure(BaseModel):
    success: Literal[False] = False
    error: str

Result = Union[Success, Failure]
```

**Priority: High** — one of the most common sources of "impossible" runtime states.

### H7b — Double `| null`

Redundant nulls (`User | null | null`, `string | null | undefined`) suggest
confusion about the data model — is "missing" null, undefined, or both? Each
`| null` is a branch callers must handle. Choose ONE representation per codebase
and normalize at boundaries.

**Priority: Medium** — noisy code, rarely a crash.

### H7c — `as unknown as T` Chains

`as unknown as T` is the type-system equivalent of `// safety off`. Every
instance is a leak: the runtime value might not satisfy `T`, and nothing catches
it until `user.email.toLowerCase()` throws on an object with no `email`.

Replace with a Zod `.parse()` at the boundary: `UserSchema.parse(response.data)`.

**Priority: High** — track the count; aim for zero.

### H7d — `dict[str, Any]` for Known Shapes

`dict[str, Any]` tells the type system "I don't know what this is" — but the
code that follows clearly *does* know the shape. Every field access is a
potential crash the checker can't see.

**Bad**:

```py
def process_item(raw: dict[str, Any]) -> ItemPayload:
    return ItemPayload(
        name=raw.get("name", ""),
        price=raw.get("price", 0),
        # a typo in "price" becomes a silent zero
    )
```

**Good**:

```py
class RawItem(BaseModel):
    name: str
    price: float
    description: str | None = None

def process_item(raw: RawItem) -> ItemPayload:
    return ItemPayload(name=raw.name, price=raw.price)
```

**Priority: High** — extremely common in data pipelines. Each occurrence is an
untyped boundary that silently produces bad data.

### H7e — Sentinel Values Instead of Absence

**The idea.** `undefined != null != ""` — each has a distinct meaning (key
absent, present-but-no-value, present-and-empty). A sentinel collapses "no
value" into the same type as a real value, so every consumer must know the magic
constant out-of-band, `min(1)`-style constraints can't express the real
invariant, and the schema can't reject the sentinel as invalid input. It is
worse when the sentinel is manufactured in only one code path — that hides the
"no value" case inside a normal-looking type instead of surfacing it as a state.

**Bad**:

```py
class UserResponse(BaseModel):
    device_id: str  # "" means "no device credential"

def from_user(cls, user: User, device_id: str = "") -> Self: ...
```

```ts
device_id: z.string()   // "" silently accepted as a valid value
```

**Good** — `None`/`null` at both boundaries, no transform layer papering over
the mismatch:

```py
class UserResponse(BaseModel):
    device_id: str | None

def from_user(cls, user: User, device_id: str | None = None) -> Self: ...
```

```ts
device_id: z.string().min(1).nullable()   // empty string now rejected
```

**Priority: High** — same failure mode as H7a: a real "no value" state smuggled
into a type that looks like a normal value.

---

## H8 — Partial Functions and Escape Hatches

**The idea.** Haskell calls a function partial when it is undefined for some
inputs its type admits (`head []`). Rust makes the same thing loud and
greppable: `.unwrap()` means "I claim this can't fail" and lint culture treats
each one as a claim needing justification.

Python and TypeScript have the same construct wearing quieter clothes. These are
all assertions of a fact the checker could not prove:

| Escape hatch | What it claims |
|---|---|
| `typing.cast(T, x)` | "trust me, this is a `T`" — zero runtime effect |
| `# type: ignore` (bare) | "trust me about this whole line, whatever breaks" |
| `assert x is not None` | "this is populated" — and it's stripped under `-O` |
| `.one()` / `.scalar_one()` | "exactly one row exists" — raises otherwise |
| `xs[0]`, `d[k]` | "non-empty" / "key present" |
| TS `x!` | "not null" — erased at compile time, checks nothing |
| `@ts-expect-error` | same as bare `# type: ignore` |

**Why it matters.** `cast()` is `as` wearing a function call: it has *no*
runtime effect, so a wrong cast produces exactly the crash the annotation
promised was impossible — just later, and somewhere else. A bare `# type:
ignore` is worse than a scoped one: it suppresses every current *and future*
error on that line, so an unrelated regression lands silently.

**What to replace with**, in order of preference:

1. **Prove it instead of asserting it** — narrow with a check the checker
   understands (`if x is None: raise`), so the type refines naturally.
2. **Parse it** (H2) — if the value comes from IO, a Pydantic model or Zod
   schema turns the claim into a verified fact.
3. **Scope the suppression** — `# type: ignore[assignment]` or
   `# pyright: ignore[reportFoo]` over a bare ignore, so only the known error
   is silenced.
4. **Keep it, with a comment** — some are legitimate (a library's stubs are
   wrong; a `cast` immediately after an `isinstance` chain the checker can't
   follow). Legitimate escape hatches should say *why* in a comment.

**Priority: High** — each one is an unverified claim, and unlike `Any` they look
like ordinary code.

---

## H9 — Immutability by Default

**The idea.** Rust's ownership model exists to answer one question statically:
*who is allowed to change this, and when?* Python and TypeScript can't enforce
that, but they can express the common case — "nobody changes this after
construction" — and that alone removes most aliasing bugs.

**Bad**:

```py
def add_tag(item: Item, tags: list[str] = []) -> Item:   # shared across calls
    tags.append(item.name)                                # mutates the default
    ...

def normalize(items: list[Item]) -> None:
    items.sort(key=...)      # caller's list reordered; nothing in the signature says so
```

```ts
const DEFAULTS = { retries: 3 };
function run(opts = DEFAULTS) { opts.retries = 0; }   // mutates the shared default
```

**Good**:

```py
@dataclass(frozen=True)
class OrderCore:
    total: Decimal

class Config(BaseModel):
    model_config = ConfigDict(frozen=True)

def add_tag(item: Item, tags: Sequence[str] | None = None) -> Item: ...
    # Sequence, not list — the signature no longer promises mutability

def normalize(items: Sequence[Item]) -> list[Item]:
    return sorted(items, key=...)    # returns new; caller's list untouched
```

```ts
type Config = { readonly retries: number; readonly hosts: readonly string[] };
const DEFAULTS = { retries: 3 } as const;

function normalize(items: readonly Item[]): Item[] {
  return [...items].sort(compare);
}
```

Note the parameter-type half: accepting `Sequence[str]` / `readonly T[]` instead
of `list[str]` / `T[]` is a *documented promise not to mutate*, enforced by the
checker. That's the transferable part of ownership.

**When NOT to use**: hot loops building large collections incrementally; ORM
model instances, which are mutable by design.

**Priority: Medium** — prevents a real bug class (shared mutable default
arguments are a perennial Python footgun), but rarely the cause of an outage.

---

## H10 — Range and Shape Constraints

**The idea.** Ada's contribution to type design isn't fancy generics — it's
subtypes with declared ranges: `type Percentage is range 0 .. 100`, checked at
every assignment. Most numeric values in real code have a legal range, and
almost none of them say so.

The tell is a bound that exists **only in a docstring, a comment, or a
function body**. If the code clamps, normalizes, or asserts a range somewhere,
that range is part of the type and is currently being carried out-of-band.

**Bad** — the bound is real but lives in prose:

```py
def distance_to_score(distance: float) -> float:
    """``max(0.0, 1.0 - distance)`` — clamps to a floor of 0.0."""
    return max(0.0, 1.0 - distance)

class ItemScore(BaseModel):
    score: float          # provably in [0, 1] upstream; the type admits -4e9

class TasteExplanation(BaseModel):
    vector: list[float]   # docstring says "length 512"; the type says any length
```

**Good** — the bound is in the type, and Pydantic enforces it at the boundary:

```py
from typing import Annotated
from pydantic import Field

Score = Annotated[float, Field(ge=0.0, le=1.0)]
CosineDistance = Annotated[float, Field(ge=0.0, le=2.0)]
TasteVector = Annotated[list[float], Field(min_length=512, max_length=512)]

class ItemScore(BaseModel):
    score: Score
```

```ts
const ScoreSchema = z.number().min(0).max(1);
const EmbeddingSchema = z.array(z.number()).length(512);
```

**The dimension case is the highest-value one.** A vector length is the single
most load-bearing invariant in embedding code and the easiest to violate
silently — a 256-dim vector flowing into a 512-dim space produces wrong
results, not a crash. Prefer tightening a shared alias (`TasteVector = ...`) in
one place over annotating call sites: one edit, whole-codebase effect.

**Caveat specific to this repo**: pyright `exclude`s
`src/fitted_backend/ml`, which is exactly where the range-bearing floats and
vectors live. Static checking will not see these annotations there — but
Pydantic `Field` constraints are *runtime* validation, so they still fire at
the boundary. That makes H10 more valuable in `ml/`, not less. Consider
reporting the exclusion itself as a Step 1b config finding.

**When NOT to use**: values whose "range" is a business rule that changes
independently of the type (a configurable threshold); intermediate arithmetic
results, where an out-of-range value is a legitimate transient.

**Priority: High** — cheap (one `Annotated` per alias), Pydantic-native, and it
converts an invariant that currently exists only in a docstring into one the
system enforces.

---

## H11 — Constructor Discipline

**The idea.** In ML-family languages, a module signature can expose a type
while hiding its representation: callers cannot build one directly, only
through functions that enforce the invariant. That is what makes "parse, don't
validate" (H2) *enforceable* rather than merely encouraged — without it, the
refined type is one hand-construction away from being a lie.

```ocaml
module Email : sig
  type t                          (* representation hidden *)
  val parse : string -> t option  (* the only way in *)
  val to_string : t -> string
end
```

Neither Python nor TypeScript can hide a representation. What they *can* do is
concentrate construction in one place and treat every construction elsewhere as
a finding.

**Bad** — the brand is a cast anyone can write, so the guarantee is decorative:

```ts
type UserId = string & { __brand: "UserId" };

// in a component, far from any validation:
const id = params.userId as UserId;   // no check ran; the brand proves nothing
```

```py
Score = Annotated[float, Field(ge=0.0, le=1.0)]
raw = ItemScore.model_construct(score=-3.0)   # skips validation entirely
```

**Good** — one owning module exports a parse function; everyone else calls it:

```ts
// lib/ids.ts — the only file that may mint a UserId
export function parseUserId(raw: string): UserId {
  if (!UUID_RE.test(raw)) throw new Error(`not a user id: ${raw}`);
  return raw as UserId;          // the single sanctioned cast
}
```

```py
# the sanctioned entry point; model_construct is reserved for trusted internals
score = ItemScore.model_validate({"score": raw})
```

**The checkable slice** is narrow and precise: a brand cast (`as SomeBrand`, a
`NewType(...)` call) or a validation-skipping constructor (`model_construct`,
`model_config = ConfigDict(validate_assignment=False)` on a boundary model)
appearing **outside** the module that owns the corresponding parse function.
That is decidable from the file path alone.

The broader idea — making the raw constructor unreachable by convention across
the whole codebase — **awaits a project decision** (do parse functions become
the only public constructor for refined types, and where do they live?). Until
that decision exists, do not open findings against ordinary model construction;
only against sanctioned-cast leakage as defined above.

**Priority: Medium** — it protects guarantees H2/H6/H10 have already
established. Without it, those three degrade quietly over time.

---

## Concepts we document but do not check

These are real ideas from the same tradition. They are here because they inform
judgment on `INVESTIGATE` findings — but they are deliberately **not** in
[`type-checks.md`](type-checks.md), because their findings are ones nobody
would act on in a Python + TypeScript app. Do not open findings against them.

### Phantom types

A type parameter that appears in the type but nowhere in the runtime data. It
exists purely to make the checker distinguish two things that are byte-identical
at runtime.

```ts
type Tagged<T, Tag> = T & { readonly __tag: Tag };  // __tag never exists at runtime
```

**H6 branded types *are* phantom typing applied to identity** — so this concept
is already half-adopted. The other axes it generalizes to: units of measure
(also folded into H6), and encoding processing state, e.g. `Html<Escaped>` vs
`Html<Raw>` so an unescaped string can't reach a renderer.

### Typestate

Encode an object's *lifecycle state* in its type, so calling a method in the
wrong state doesn't compile. Rust's canonical version consumes the value on
transition, so the stale handle is unusable:

```ts
type Conn<S extends "open" | "closed"> = { socket: Socket } & { __state: S };
declare function send(c: Conn<"open">, msg: string): void;
declare function close(c: Conn<"open">): Conn<"closed">;
// send(closedConn, "hi")  → type error
```

This is H1 extended over *time* rather than over a single snapshot. Excluded
from the checks because it needs linear/affine types to be sound: Rust has them,
Python and TypeScript do not, so nothing stops you from reusing the pre-close
value. Python's `Generic[StateT]` spelling also reads as line noise. Our real
bug classes are boundary parsing, not state machines.

### Parametricity ("theorems for free", Wadler)

The more generic a signature, the fewer implementations it admits — so the type
itself tells you more:

```ts
function f<T>(xs: T[]): T[]        // cannot invent elements; only reorder/drop/duplicate
function f(xs: Item[]): Item[]     // could do anything — fetch, mutate, construct
```

The practical corollary is real: a helper that takes `Item` but only reads `.id`
becomes more honest as `<T extends { id: number }>(x: T)`. Excluded from the
checks because it isn't greppable and reviewers almost never act on it.

### Dependent types

In Idris, Agda and Lean, a type can depend on a *value*: `Vector 512 Float` and
`Vector 256 Float` are different types, so a dimension mismatch is a compile
error and a proof of correct length rides along with the data. For embedding
work this is the exact tool for the exact job — and it is exactly what Python
and TypeScript cannot express.

What transfers is the *discipline*, which is H10: put the dimension in the type
as a constraint, enforce it once at the boundary where the vector is
constructed, and stop re-checking it downstream. What does not transfer is the
guarantee — `Field(min_length=512)` is a runtime check at one point, not a
proof carried by the value. Don't pretend otherwise in a finding's wording.

TypeScript can fake a narrow slice of this with tuple types
(`[number, number, number]`) and literal-typed generics, but a 512-element
tuple is not a serious proposition. Note the idea, use H10, move on.

### Let it crash (Erlang / Elixir)

Erlang is dynamically typed and famously reliable, because reliability came
from supervision trees and process isolation rather than from types: a worker
that hits an unexpected state dies and is restarted clean, and correctness lives
in the *recovery structure* instead of in the *prevention structure*.

This is the deliberate counterweight to everything else in this document. Types
eliminate the bug classes they can see; a supervision strategy handles the rest,
including every class they can't. Both are real, and over-investing in the first
because it feels rigorous is its own failure mode.

Concretely: the pipeline integrations are more Erlang-shaped than
Haskell-shaped. Partial failure there is the normal case, not an exception —
a store changes its markup, one source 429s, one item has a malformed price.
The right posture is isolate-and-retry the failing unit, not a type that makes
the failure unrepresentable. This is also why "errors as values" below is out of
scope rather than merely unimplemented.

### Errors as values

Rust has no exceptions: fallibility is in the return type (`Result<T, E>`) and
the checker forces you to handle it. Python and TypeScript hide fallibility
entirely — nothing in `def fetch(url: str) -> Item:` says it can raise.

Deliberately out of scope: adopting `Result` wholesale fights FastAPI and Celery
idiom (both are built around exceptions propagating) and would generate a
finding on every `raise`. Worth revisiting only if scoped to one subsystem —
the pipeline integrations, where partial failure is the normal case and is
currently expressed by convention rather than by type — and see "let it crash"
above for why that may be the right answer there anyway.

### Specification, not typing (TLA+ / Alloy)

Some invariants are not properties of a value, so no type system reaches them.
The product invariants in root `CLAUDE.md` are all of this kind:

- a user never receives more than 3 notifications per week
- an item shown is never shown again within `ITEM_COOLDOWN_DAYS`
- items are never deleted, only `in_stock`-toggled
- the pipeline is idempotent on `(external_id, source_id)`

Each is a statement about *sequences of states over time*, or about a
relationship between separate records — TLA+ and Alloy exist to check exactly
these, and neither Pydantic nor Zod can encode any of them.

**This is the boundary between `/type-health` and `/write-tests`.** Do not open
findings against these; when a scan brushes against one (a cooldown constant, a
notification counter), note "invariant — belongs in property-based tests" and
move on. The affordable 80% is property-based testing (Hypothesis on the
backend, fast-check on the frontend), which is `/write-tests`' territory. The
useful discipline this contributes to *this* skill is the negative one: knowing
when to stop tightening a type because the property in question was never
expressible as one.

---

## Priority Summary

| Priority | Heuristics | Rationale |
|----------|-----------|-----------|
| **High** | H1 (illegal states), H2 (parse don't validate), H3 (precision), H4 (exhaustiveness), H7a (boolean blindness), H7c (`as unknown`), H7d (`dict[str, Any]`), H7e (sentinel values), H8 (escape hatches), H10 (range and shape) | Directly prevent crashes and data corruption |
| **Medium** | H5 (boundary vs core), H6 (branded types), H7b (double `null`), H9 (immutability), H11 (constructor discipline) | Improve maintainability; catch subtle bugs |

---

*Based on: Scott Wlaschin "Designing with Types", Alexis King "Parse, Don't
Validate", Yaron Minsky "Effective ML", Chris Krycho "Making Illegal States
Unrepresentable in TypeScript", the Rust API Guidelines / `clippy`
`unwrap_used` lint rationale, the Ada/SPARK subtype and dimensional-analysis
model, Edwin Brady "Type-Driven Development with Idris", Joe Armstrong's
"let it crash" thesis, and Leslie Lamport "Specifying Systems" (TLA+).*
