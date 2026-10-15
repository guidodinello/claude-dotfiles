# Docs folder templates

Templates the `ios-sim` skill fills in Bootstrap mode and updates on every run. Replace every `<...>`. Keep it short: these are maps, not reports. Credentials are always pointers.

## `README.md` (index + project profile)

```markdown
# ios-sim: iOS Safari checks for <project>

Verifies web UI in real iOS Safari in the Xcode Simulator. Method lives in the `ios-sim` skill; this folder holds what is specific to <project>.

## Contents

| Path | What it covers |
|---|---|
| `screens.md` | Screens worth checking, known iOS traps per screen, lessons |
| `runs/README.md` | One folder per run: refs, versions, measurements, screenshots |

## Profile

| Field | Value |
|---|---|
| Default device | <name> (<udid>) |
| Default runtime | iOS <version> |
| Front URL reachable from the simulator | <http://127.0.0.1:PORT> (the simulator shares the host loopback) |
| Start the front for this check | <command, working directory, ready signal> |
| Run a second front instance (base worktree) | <port, env, dev-server proxy if the backend allows CORS from one origin only> |
| Dependency install in a fresh worktree | <for example `pnpm install`> |
| Backend / API for this check | <how to start it, seeded with synthetic data> |
| Login | <route>, selectors `<user>` / `<password>` / `<submit>` |
| Credentials (pointer only) | <seeder class, env var name, or doc reference. Never a password> |
| Login alternative | <project-provided login or seed URL, or none> |

## Last updated

<YYYY-MM-DD> by run `runs/<run>/`.
```

## `screens.md`

```markdown
# Screens and iOS traps

| Screen | URL | Needs login | What to measure | Known iOS trap |
|---|---|---|---|---|
| <name> | <path> | yes/no | <overflowPx, safe-area bottom, ...> | <for example root uses `100vh`> |

## Lessons

- <YYYY-MM-DD> <what was learned, one line, with the run link>
```

## `runs/README.md`

```markdown
# Runs

| Run | Change | Base | PR | Result |
|---|---|---|---|---|
| [YYYY-MM-DD-<change>](YYYY-MM-DD-<change>/README.md) | <one line> | <sha7> | <sha7> | <one line> |
```

## `runs/YYYY-MM-DD-<change>/README.md`

```markdown
# <change>: iOS Safari check (YYYY-MM-DD)

## Environment

| Item | Value |
|---|---|
| Base / PR | <sha> / <sha> |
| Device | <name> (<udid>) |
| iOS runtime | <version (build)> |
| Xcode | <version (build)> |
| Safari | <version, from the user agent> |

## Measurements

| Screen | Metric | Base | PR |
|---|---|---|---|
| <screen> | `100vh` / `100dvh` | <n> / <n> | <n> / <n> |
| <screen> | `overflowPx` | <n> | <n> |
| <screen> | safe-area bottom | <n> | <n> |

## Screenshots

| File | What it shows |
|---|---|
| `01-<description>.png` | <one line> |

## Verdict

<one or two lines: what changed, what is still open>
```

Screenshots are named `NN-description.png` and sit next to this file. Use synthetic data only: discard any screenshot that could show real data.
