# Mapping guide

## Explorer prompt skeleton (one per repo group, run in parallel, read-only)

> Very thorough, read-only. Build a code-grounded inventory of every EXTERNAL system {repos} talk to, plus internal structure, for an architecture diagram. Cite file paths relative to the workspace root. Mark anything ambiguous "unverified".
> PRIVACY: output system names, module names, endpoint paths, env var NAMES and file paths only. Never copy env values, secrets, tokens, payloads, fixtures or person data.
> Return: (A) per external system: purpose; each interaction as an edge with direction, mechanism (REST, SDK, webhook, queue, cron poll, DB, OAuth/JWT exchange, iframe/navigation), data CATEGORY, code anchor (file + class/function), env var names, which deployable runs it. (B) internal structure: deployables and how they relate, modules with one-line responsibility, key flows between modules with anchors, which modules call which externals. (C) frontend surface and auth between frontend and backend. Include negative findings (installed but unused SDKs, permissions without resources).

Split typically: backend (all deployables) in one agent; frontends + infra/terraform + CI in another.

## Data schema (`VIEWS` in the template)

| Object | Fields |
|--------|--------|
| view | `viewBox`, `hint`, `intro {eyebrow,title,paras[],start?[edgeIds]}`, `nodes[]`, `edges[]`, `flows?[]` |
| node | `id, kind (person|ext|self|ours|ghost), x,y,w,h, label, sub, lines?[], codeLines?, cta?, major?, drill? (view id), up? (context node id), desc[], code[{p,n}], modules?[[name,desc]], crons?[[schedule,desc]], routes?[], unverified?[]` |
| edge | `id, from, to, kind (rest|webhook|auth|data|nav|ops), label, off?, t?, both?, mech, flows, runs, code?[], warn?, unverified?[]` |
| flow | `id, label, title, edges[edgeIds], steps[{t, c[paths]}]` |

`code.p` starts with a key of `REPOS`; `gh()` turns it into a GitHub blob link.

## Layout rules

- Context view: self node in the middle; the dominant external system next to it with the widest gap; people on the far left; minor externals around the rim. Inside view: entry points left, api center, workers/schedulers right, data stores bottom, one `ghost` box for all externals on the far right.
- Leave >=130px between boxes where a label pill sits; pills center on the clipped segment (`t` moves them along it).
- Parallel edges between the same pair: `off` of ±14 to ±45 so lines and pills don't overlap.
- A line must not cross a third box: check the line's x at the third box's top/bottom y.
- Every relationship mentioned in panel prose must also exist as an arrow. Users read the arrows first.

## Verification commands

```bash
# every cited path exists
rg -o '"((repoA|repoB)/[^"]+)"' -r '$1' map.html | sort -u | while read p; do [ -e "$p" ] || echo "MISSING $p"; done
# script parses
awk '/^<script>$/{f=1;next}/^<\/script>$/{f=0}f' map.html > /tmp/x.js && node --check /tmp/x.js
```
