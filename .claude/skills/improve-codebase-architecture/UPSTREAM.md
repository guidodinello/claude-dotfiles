# Upstream provenance

This skill is vendored from [mattpocock/skills](https://github.com/mattpocock/skills),
path `skills/engineering/improve-codebase-architecture`, MIT license,
Copyright (c) 2026 Matt Pocock. Attribution and the license apply to every file
in this directory that came from there; the upstream permission notice is vendored
unmodified as [`LICENSE`](LICENSE).

## Pinned source

| Item | Value |
|---|---|
| Upstream repo | `mattpocock/skills` |
| Pinned upstream commit | `b843cb5ea74b1fe5e58a0fc23cddef9e66076fb8` |
| Vendored here in | `f043af3` (2026-05-04) |

## What matches upstream

- `SKILL.md` as vendored in `f043af3` is byte-identical to upstream at `7afa86d`
  (2026-04-28, the newest upstream commit that touched the skill directory) and
  therefore at every upstream commit from `7afa86d` through the pinned
  `b843cb5`. Earlier upstream commits (`f76e3ba`, `fb847c6`, `62f43a1`) differ.
- `DEEPENING.md`, `INTERFACE-DESIGN.md` and `LANGUAGE.md` as vendored in
  `f043af3` are byte-identical to upstream at all four upstream commits that
  touched the directory, so no range narrows them further.
- `ADR-FORMAT.md` and `CONTEXT-FORMAT.md` come from upstream's
  `skills/engineering/grill-with-docs/` at `b843cb5`, unmodified. `SKILL.md`
  links to them, and upstream's `grill-with-docs` skill is not vendored here.

## Local edits

- `9dada94`: `LANGUAGE.md` emphasis markers changed for markdownlint; `SKILL.md`
  gained the instruction to explore from the integration branch.
- #126: `SKILL.md` links to the vendored format
  files in this directory instead of a missing `../grill-with-docs/`, and the
  description line is shortened.

## Updating

Diff each file against the same path in `mattpocock/skills` at the new commit,
re-apply the local edits above, and update the pinned commit in this file.
