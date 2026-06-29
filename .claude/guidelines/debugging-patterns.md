## Debugging Patterns

### Fix completeness verification

When fixing a bug that affects multiple consumers of a field or value, verify the fix is exhaustive before declaring done. Work in layers:

1. **Try the type system first.** Temporarily remove the field from the shared type and run the type checker. If types are tight, every access site errors — exhaustive by definition. If types are loose, move to step 2.

2. **Grep for explicit reads.** Search for the field name across the codebase. This catches property access, destructuring, and string-keyed access. This is the consumer side.

3. **Recognize the blind spot: implicit propagation.** Grep misses cases where the full object is parsed and forwarded without naming the field — e.g. `JSON.parse(blob)` returns a field silently if it's in the blob. No explicit access, no grep hit.

4. **For the supply side, grep structurally.** Instead of searching for the field name, search for the data-serving pattern — find every endpoint that returns the blob to callers. Verify each one either fetches and overlays the authoritative source, or doesn't feed any surface that uses the field.

The fix is complete when: all explicit consumers are covered (grep), and all implicit supply paths either overlay the authoritative source or are confirmed not to reach an affected surface (structural check).
