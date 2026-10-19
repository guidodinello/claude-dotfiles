---
name: system-integration-map
description: "Trigger: integration map, architecture diagram, how is our system connected, onboarding to a codebase. Build a clickable two-level map of external systems and internal modules, linked to code."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when the user wants to understand or show how a system connects to external services and how its own processes fit together: onboarding, "what does this talk to", a context or C4-style diagram, an interactive architecture page.

## Hard Rules

- Ground every node, arrow and claim in code read this session. Never fill gaps from memory, Slite or naming conventions; tag them `unverified`.
- Every arrow states direction and mechanism, and links to the file that implements it.
- Names only: system, module and env var NAMES and file paths. No env values, secrets, payloads, fixtures or person data (PHI/PII).
- Every cited path must exist (run the check in `references/mapping-guide.md`).
- Every relationship described in panel text also appears as an arrow.
- The finished map is client-confidential: keep it in the project's private notes (e.g. `my-dev-things/architecture/`) and publish it as a private artifact. Never commit it to a public repo.

## Decision Gates

| Situation | Action |
|-----------|--------|
| 4+ repos or deployables | Two parallel read-only explorers (backend; frontends + infra + CI) |
| Single small service | Map inline, skip the inside view |
| A finding contradicts the docs | Trust the code; list it under good-to-know |
| A finding is a risk (security, HIPAA) | Add `warn` on the edge and mention it in the reply; don't file anything |

## Execution Steps

1. List the repos and deployables; record branch + short SHA of each.
2. Run the explorers with the prompt skeleton in `references/mapping-guide.md`.
3. Copy `assets/integration-map.template.html`; replace the DATA block (`SYSTEM_NAME`, `REPOS`, `VIEWS`, `GOOD_TO_KNOW`), `<title>`, `<h1>` and the meta line with SHAs.
4. Lay out both views per the layout rules; add 3–6 flows that cross several boxes.
5. Run the path check and `node --check`; screenshot once if a browser is available.
6. Publish with the Artifact tool (icon `map`); add a README entry next to the source file.

## Output Contract

Return: the artifact link, where the source lives, how many systems/edges/flows were mapped, the top 3–4 surprises (the good-to-know list), and any open `unverified` questions. Say whether a visual check ran.

## References

- `assets/integration-map.template.html` — renderer with a fictional example; data lives in one `VIEWS` object.
- `references/mapping-guide.md` — explorer prompt, data schema, layout rules, verification commands.
