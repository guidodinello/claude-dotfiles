---
name: ios-sim
description: "Trigger: check in iOS Safari, iOS simulator, 100vh/100dvh, safe area, Safari toolbar, iOS-only scroll or input bug. Verifies web UI in real iOS Safari inside the Xcode Simulator, measured not eyeballed, base vs PR, with a per-project docs folder."
license: Apache-2.0
metadata:
  author: "guidodinello"
  version: "1.0"
---

## Activation Contract

Load when a web UI change must be verified in **real iOS Safari**, for bugs that only reproduce there: viewport height (`100vh` vs `100dvh`), safe areas, the Safari toolbar, iOS-only scroll and input behavior.

Not for cases Playwright WebKit already covers (layout, logic, forms, anything that does not depend on Safari chrome). Playwright WebKit with an iPhone device profile does **not** reproduce Safari's toolbar or its dynamic viewport, which is the only reason this skill exists. Not for release verification (that is `release-sim`).

## Helper script

All driving goes through one stdlib-only helper. The skill runs from the project's working directory, so always call it by its installed absolute path (`$HOME`, not `~`, so it expands inside quotes):

```bash
WIR="$HOME/.claude/skills/ios-sim/scripts/wir.py"
python3 -I "$WIR" <subcommand> <udid> ...
```

Everywhere below, `wir.py <subcommand>` means that invocation. `python3 -I` is deliberate: the helper is stdlib-only and target projects have no venv for it.

## Hard Rules

- **Synthetic data and accounts only.** Never log into production. Never put real patient or user data on screen or in a screenshot. This is a healthcare org rule (PHI): if a screen shows anything that could be real, stop, discard the screenshot, and switch to seeded data.
- **Credentials are pointers.** The docs folder records a seeder class, an env var name or a doc reference. Never a password, token or real email.
- **Local only.** Never push, never commit measurement helpers, never open a PR from this skill. The only thing written into the project workspace is the docs folder.
- **Touch no project file to measure.** Measurement and login go through `wir.py` (Web Inspector socket). Never add a snippet to an `index.html` or any source file.
- **Never stop or reuse a dev server this skill did not start.** Track the PIDs it started; stop only those.
- **Measure, do not eyeball.** Every claim in a report is a number from `wir.py measure` or a screenshot named in the run doc.
- **Shut down every simulator this skill booted** (and only those), even when a step fails.
- **Refs are SHAs.** Reports quote refs as SHAs and name the device, Xcode build, iOS runtime and Safari version.
- **Never skip logged-in screens silently.** If login cannot be driven, stop and ask (see Decision Gates).

## Decision Gates

| Gate | Check | Outcome |
|---|---|---|
| Preflight: Xcode | `xcodebuild -version` | missing: stop, tell the user to install Xcode |
| Preflight: runtime | `xcrun simctl list runtimes` shows an iOS runtime | none: stop, hint `Xcode > Settings > Components` to install one |
| Preflight: protocol | `wir.py selftest <udid>` (with `wir.py hold` already running, see Run Mode step 3) | fails: stop loudly. The private WIR protocol may have changed with a newer Xcode. Do not retry blindly and do not fall back to guessing |
| Docs folder | resolution rule below | folder exists: **Run**. Missing: **Bootstrap** |
| Login | profile says how | 1. drive the form via `wir.py fill`/`click`. 2. A project-provided login or seed URL from the profile. 3. Neither works: stop and ask the user |

### Docs folder resolution

1. An explicit path argument wins.
2. Otherwise `my-dev-things/ios-sim/` when a `my-dev-things/` folder exists at the workspace root (the git top level of the current directory).
3. Otherwise ask the user where it should live. Create nothing before they answer.

## Docs Folder Layout

```text
<docs>/
  README.md        index + project profile
  screens.md       screens worth checking, known iOS traps per screen, lessons
  runs/
    README.md      index of runs
    YYYY-MM-DD-<change>/
      README.md    refs (SHAs), device, Xcode build, iOS runtime, Safari version, table, screenshots
      NN-description.png
```

Every folder has a `README.md` (see the `dev-docs-index` skill). Templates: [references/docs-folder-templates.md](references/docs-folder-templates.md).

The profile in `README.md` holds everything project-specific: dev server URLs and ports reachable from the simulator, how to start the front for this check, how to run a **second** front instance (port, env, proxy), dependency install in a fresh worktree, how to log in (pointer only), default device and runtime. Nothing project-specific lives in this skill.

## Bootstrap Mode

1. Investigate the project: dev scripts, ports, the auth flow, seeders or fixtures, CORS and proxy config, package manager.
2. Ask the user only what the code cannot tell. One question at a time, then stop and wait.
3. Write `README.md` (profile + index), `screens.md` and `runs/README.md` from the templates.
4. Confirm with the user before the first run.

## Run Mode

1. Read the docs folder. Resolve base and PR refs to SHAs (`git rev-parse`).
2. Run the preflight gates. Pick the default device from the profile; note whether it was already booted.
3. Boot it only if needed (`xcrun simctl boot <udid>`, then `xcrun simctl bootstatus <udid> -b`). Record that this run booted it. Start `wir.py hold <udid>` in the background and record its PID: the inspector daemon exits when its last client disconnects and launchd throttles its respawn, so without a held connection chained commands fail with `Broken pipe`. Then run `wir.py selftest <udid>`.
4. Create a temporary base worktree: `git worktree add "$(mktemp -d)" <base-sha>`. Install dependencies there and start the base and PR fronts exactly as the profile says. Record the PIDs started.
5. For each screen, per ref: `xcrun simctl openurl <udid> <url>`, then `wir.py wait <udid> <url>`.
6. Log in per the gate above using `wir.py fill` and `wir.py click`. Confirm the landing URL with `wir.py eval`.
7. `wir.py measure <udid> <url>` and `xcrun simctl io <udid> screenshot <run>/NN-description.png`.
8. Build the base vs PR table, screen by screen.
9. Write `runs/YYYY-MM-DD-<change>/README.md`: SHAs, device, `xcodebuild -version`, iOS runtime, Safari version (from `userAgent` in the measure output), table, screenshot list. Append a row for it to `runs/README.md` so the run stays discoverable.
10. Fold lessons into `screens.md` (and the profile when a field was wrong or missing).
11. Cleanup, always: stop only the servers and the `wir.py hold` process this run started, `git worktree remove` the base worktree, shut down only the simulators this run booted, and check `git status` is clean outside the docs folder.

## Measurement

`wir.py measure` returns `vh`, `dvh`, `svh`, `lvh`, `innerHeight`, `visualViewportHeight`, `clientHeight`, `scrollHeight`, `maxScrollY`, `overflowPx` and the four `env(safe-area-inset-*)` values, plus the URL and user agent. It appends temporary off-screen divs and removes them in the same tick; it changes no file and leaves the page as it found it.

Safari version: take `Version/x` from the user agent. The OS in the user agent is frozen (an iOS 27.0 runtime reports `iPhone OS 18_7`), so quote the iOS runtime from `xcrun simctl list runtimes` instead. Record safe-area insets as measured; do not assume non-zero values.

Reading it: a root container taller than `dvh` shows up as `overflowPx > 0` with nothing to scroll. On the reference run (iPhone 17 Pro, iOS 27.0) `100vh` = 754 and `100dvh` = 714, so `min-h-screen` produced 40px of stray scroll that `min-h-dvh` removed.

## Output Contract

Reply in the conversation language, in chat:

```text
ios-sim: <change> on <device>, iOS <runtime>, Xcode <build>, Safari <version>
base <sha7> vs PR <sha7>
| Screen | Metric | Base | PR |
Run doc: <path to runs/.../README.md>
Lessons added: <screens.md entries, or none>
Cleanup: servers stopped ✓ · worktree removed ✓ · sim shut down ✓ · git status clean ✓
```

## References

- [references/docs-folder-templates.md](references/docs-folder-templates.md): templates for the docs folder files.
- [references/troubleshooting.md](references/troubleshooting.md): failure modes, and why safaridriver is not used.
- [scripts/wir.py](scripts/wir.py): Web Inspector socket client (`hold`, `selftest`, `pages`, `wait`, `eval`, `measure`, `fill`, `click`). Installed at `$HOME/.claude/skills/ios-sim/scripts/wir.py`.
