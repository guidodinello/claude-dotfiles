---
name: backward-trace
description: A first-principles investigation method for understanding how something actually works in a codebase. Use it whenever the task is to figure out a mechanism rather than make a known edit — "how does X work?", "where does this value come from?", "what can trigger / cause / produce Y?", "what are all the places that do Z?" — and as a required pre-step before tightening, gating, removing, or otherwise changing any shared or cross-cutting behavior, where missing one caller or one writer would be a bug. Reach for this even when the user doesn't ask for an "investigation" — any comprehension question about an unfamiliar flow qualifies. Do NOT use it for routine edits, renames, or single-file changes where the mechanism is already understood.
---

# Backward-trace investigation

## Why this exists

The fast, tempting way to answer "how does X work?" is to pattern-match: assume the code follows the convention you'd expect, and describe that. In any non-trivial codebase that's a trap — real systems diverge from their own apparent patterns in ways that bite exactly when you trust the pattern:

- **The schema you assume isn't the schema in play.** ORMs, migrations, and the live database drift apart; the type or model in the code describes intent, not the rows that actually exist.
- **One config, many consumers.** Behavior you "confirmed" in one entry point, build target, or environment may diverge in another that shares the same config.
- **Dead code.** Files, barrel re-exports, and over-exported symbols that look load-bearing but aren't.
- **Loosely-typed blobs.** JSON/serialized columns, `any`-typed payloads, and dynamic fields whose real shape in production often differs from the interface that describes them. Before tracing a flow that reads such a blob, inspect a real value — don't reason from the type alone.

So the answer can't come from "how this kind of thing usually works." It has to come from the actual artifact and the actual code path that produced it. This method is a disciplined backward walk that ends in a *provably complete* set of entry points — not a plausible-sounding guess.

## The method

Work backward, one verified link at a time, from a real thing you can see to the complete set of things that produce it.

### 1. Anchor on a concrete observable, not a pattern

Start from the real artifact: the actual API response body, the actual value in the row, the exact rendered string, the specific 403 with its specific message. Capture it. This is your ground truth and your stopping condition — you're done when you can explain *this*, not when you've described something that sounds like it.

Avoid "it probably works like a typical X." If you catch yourself describing a mechanism you haven't yet seen in the code, stop and go find it.

### 2. Find the immediate producer

What is the *last* code that touched this observable before you saw it? Find it — grep for the string, the field name, the status code, the column. Read it. Don't infer it from the shape of the output.

### 3. Walk backward one link at a time

For the producer you just found, ask: **what feeds this?** Find that in code and confirm it before moving up another level. Each step is a small, verifiable claim — "this value comes from `mapOrder()` at `services/orders.ts:88`, which reads `row.data`" — not a leap across the whole stack.

### 4. At every branch, enumerate ALL sources — this is the core discipline

The point where guessing creeps back in is assuming there's only one source. There usually isn't. At each link, name and **run** the search that proves the set is complete:

- every caller of this function — `grep` the function name across the repo
- every route that mounts this handler
- every writer to this column / setter of this field
- every UI surface or entry point that hits this endpoint

Then state the conclusion as a closed set with its evidence:

> The entry points are {A, B, C}, found via `grep -rn "doThing(" src`, and this is exhaustive because that grep covers every call site and each one routes through here.

Never write "the entry point is X" when you only looked at the first hit. If a search can't prove completeness (dynamic dispatch, string-built names, reflection), say so explicitly and name what you couldn't rule out — an honest gap beats a false "all."

### 5. Only then analyze

With the complete entry-point set in hand, the analysis can finally be exhaustive instead of representative. Now you can answer the real question — what changes, who's affected, where the bug is — against the whole set, not a sample of one.

## Before you conclude — discipline checklist

- **Did I verify each link, or assume it?** Every step in the chain should cite a `file:line` you actually read.
- **Can I name the search that makes my entry-point list provably complete** — or am I just hoping there's only one source? If the latter, go run the search.
- **Am I reasoning from the actual artifact, or from "how this kind of thing usually works"?** If you can't point to the observable you started from, you've drifted back into pattern-matching.

## Worked shape (not a script — adapt it)

> **Q:** Why does this record display a fallback value ("Unknown") instead of the real name?
>
> 1. *Observable:* the API returns `name: undefined` in the serialized `data` blob for record `#1234` (saw the actual response, not a cached/admin view).
> 2. *Immediate producer:* the UI reads `record.data.name`; the API serializes `row.data` verbatim — grep'd the response field back to the mapper.
> 3. *Walk back:* `row.data` is written at record-creation time; the column is a parsed JSON blob, not a dedicated `name` column.
> 4. *Enumerate writers:* `grep -rn "data:" src/.../records` → three create/update paths write `data`. Two set `name`; one (an alternate ingestion path) doesn't. That set is complete because all writes go through these three.
> 5. *Analyze:* records created via that one path have no `name` in the blob → the fallback shows. The fix targets that one writer, and the conclusion holds for every affected record, not just `#1234`.
