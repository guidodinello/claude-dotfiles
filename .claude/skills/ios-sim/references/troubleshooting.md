# Troubleshooting

## Why `wir.py` and not safaridriver, Playwright or GUI control

Verified on 2026-10-15 (Xcode 27.0 build 27A266a, iOS 27.0 runtime 24A434, Safari 27.0.1). Do not retry these blindly.

| Path | What happened |
|---|---|
| `safaridriver` + `safari:useSimulator` | `session not created: Could not find any session hosts that match the requested capabilities`, even with the simulator already booted and `safari:deviceUDID` set. With `platformName: iOS` alone: `Some devices were found, but could not be used`. |
| `safaridriver` on macOS (control) | `You must enable 'Allow remote automation'`. Fixing it needs `safaridriver --enable`, which asks for admin rights. Never run it from this skill. If the user wants to try anyway, they run `sudo safaridriver --enable` themselves; simulator host discovery would still be unproven. |
| Writing Safari / webinspectord preferences in the simulator | No effect on session creation. |
| GUI control (`orca computer`) | Xcode 27 ships no `Simulator.app` window, and `simctl` has no input subcommand. |
| Playwright WebKit, iPhone profile | Runs, but has no Safari toolbar and a different dynamic viewport, so it cannot reproduce the bugs this skill targets. |
| **Web Inspector socket (`wir.py`)** | Works: no admin rights, no project file. |

## How `wir.py` works

The simulator exposes a user-owned unix socket: `xcrun simctl getenv <udid> RWI_LISTEN_SOCKET`. Frames are a 4-byte big-endian length followed by a binary plist carrying the WebKit Remote Inspector RPC. The client lists connected apps, picks `com.apple.mobilesafari`, lists its pages, sets up a socket to one page, and sends `Runtime.evaluate` (wrapped in `Target.sendMessageToTarget`).

This protocol is **private and undocumented**. It works on the versions above and may change in a future Xcode. That is why `selftest` is a preflight gate: when it fails, stop and report the Xcode and runtime versions. Fallbacks are limited to a project-provided login or seed URL for authentication, or stopping and asking the user.

## Why `wir.py hold` exists

`webinspectord` exits when its last client disconnects ("Shutting Down, last client disconnected" in the simulator log), and launchd throttles the respawn of a daemon that exits right away. Measured on 2026-10-15: a command run after an idle gap of 10s or more succeeds at once; a command chained straight after another fails with `Broken pipe` or an empty tab list, and retrying every second keeps it failing. With `wir.py hold` running in the background, 8 of 8 back-to-back commands succeeded. Always start it before `selftest` and stop only that PID at cleanup.

## Common failures

| Symptom | Cause and fix |
|---|---|
| `Broken pipe`, or `inspector kept failing`, or `Safari reported no tabs` | The inspector daemon was respawning. Start `wir.py hold <udid>` in the background, or wait ~10s between commands. |
| `simctl openurl <udid> about:blank` fails with `LSApplicationWorkspaceErrorDomain` 115 | `about:blank` is rejected. `selftest` launches Safari with `simctl launch <udid> com.apple.mobilesafari` instead. |
| `cannot read RWI_LISTEN_SOCKET` or empty value | The device is not booted. `xcrun simctl boot <udid>` and `xcrun simctl bootstatus <udid> -b`. |
| `no Safari tab matches ...` | Safari has not loaded the page yet (use `wir.py wait`), the URL substring is wrong, or the page redirected. The error lists the open tabs. |
| `selftest` fails with no tab | Safari shows no inspectable tab. `selftest` launches Safari itself; if it still fails, stop and report the Xcode build and iOS runtime (the private protocol may have changed). |
| Page loads on the host but not in the simulator | Use `127.0.0.1`, not a hostname the simulator cannot resolve. The simulator shares the host loopback, so a dev server bound to `localhost` or `127.0.0.1` is reachable. |
| Login form fills but app state stays empty | React-controlled input. `wir.py fill` uses the native value setter plus `input` and `change` events; setting `.value` directly does not update React state. |
| Login succeeds on a second front instance but API calls fail | The backend allows CORS from one origin only. The profile's second-instance field needs a dev-server proxy. |
| `measure` numbers look off after navigation | The tab was still loading. `wir.py wait <udid> <url>` first, then measure. |
| Leftover booted simulator | `xcrun simctl list devices booted`, then shut down only the ones this run booted. |
