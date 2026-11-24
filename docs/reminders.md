# Reminders (spec, v1)

Status: implemented in `.claude/hooks/reminders.py` and `.claude/skills/remind/`. Tests: `tests/test_reminders.py`.

## Problem

Some work can't be done now because it depends on something in the future: "after the Figma MCP limit resets, call `get_variable_defs` for the 16 component sets". Today that plan lives in a README and in one session's context. If nobody remembers to come back, the plan is lost.

A reminder brings the plan back on its own, in the right session, once it is due.

## Map

```
 /remind skill ──writes──▶ <config>/reminders/<id>.json ◀──reads/updates── reminders.py (hook)
       │                          │                                            │
       │                          └──points to (absolute path)──▶ plan doc     ├─ SessionStart
       └─ remind.py CLI: add | plan-path | list | done | snooze                └─ UserPromptSubmit
```

- **Reminder file**: one JSON file per reminder in `<config dir>/reminders/` (usually `~/.claude`; each `CLAUDE_CONFIG_DIR` keeps its own, next to the transcripts its session ids refer to). It holds a trigger and a pointer. It never holds the plan itself.
- **Plan doc**: the file that already describes the work (for example `my-dev-things/designs/README.md#after-mcp-reset`). It stays the only source of truth. When no project doc describes the work, the plan goes in `<config dir>/reminders/plans/<id>.md` (decision 11), never in a folder a session picks itself.
- **`remind.py`**: the CLI behind the `/remind` skill (add, list, done, snooze). It lives in `.claude/skills/remind/scripts/`.
- **`reminders.py`**: the hook, in `.claude/hooks/`. It imports the reading code from `remind.py`, the same way `dev-docs-index-check.py` reuses `check_index.py`.

## Decisions

1. **No daemon.** The hooks check what is due lazily: `now >= due`, at `SessionStart` and `UserPromptSubmit`. A reminder whose date passed while the laptop was off fires at the next session or prompt. On macOS a scheduler would be launchd, and `man launchd.plist` says a missed `StartCalendarInterval` run only catches up after the machine wakes from sleep, not after it was powered off. A daemon would only add push notifications, which are out of scope.
2. **Dates only in v1.** A later `when_cmd` check (for example "PR #118 merged") runs only after `due` has passed, never instead of `due`. That way the check never runs on every prompt, and every reminder still has a date to fall back on.
3. **A reminder is a trigger plus a pointer.** `plan` is an absolute path, optionally with an `#anchor`, so any session can resolve it whatever its cwd. Reminders are local to one machine (see 7), so an absolute path is never a problem.
4. **Two tiers.**
   - **Digest** (every session, at `SessionStart`): one line per reminder that is due, with its title, project and `claude --resume <session_id>`, but no plan content. That way no other session takes on the work by accident.
   - **Payload** (owning session only): "Reminder `<id>` is due: read `<plan>` and do it. Close it with `remind done <id>` when it's finished."
   - Reminders that aren't due yet appear only as one summary line: `N scheduled, next: <date>`.
5. **Matching the owner.** A reminder stores both `session_id` and `cwd`. The payload goes to the session whose id matches. If only the cwd matches (a forked session gets a new id), that session's digest line is marked `same project`; it gets no payload. A skill doesn't know its own session id, so the `SessionStart` hook prints `session_id: <id> (remind command: python3 -I <abs path>/remind.py)` into the context, and `/remind` reads both from there. The absolute command matters: the permission allow rule matches the literal command, so a `~/` spelling would prompt.
   - **The owner session's transcript can be gone.** Claude Code deletes old transcripts (`cleanupPeriodDays`). Before printing `claude --resume <id>`, the digest checks that the transcript file exists. If it is gone, the digest prints `owner session gone: start fresh in <cwd>` instead. Decision 9 is what makes that fresh start work.
6. **Deliver once, close explicitly.** Each session gets the payload once. Its id is then added to `delivered_to`, so the reminder never fires again on every prompt. A reminder that was delivered but not closed stays in the digest, marked `delivered, not done`, so it can't disappear silently. (The session receiving the payload doesn't also get a digest line for it.) It is closed with `remind done <id>` or pushed to a later date with `remind snooze <id> <duration|date>`.
7. **Storage stays on this machine.** `<config dir>/reminders/` is neither synced nor copied by `sync.sh`, because session ids only exist on the machine that created them.
8. **Scope compared with `PENDING.md`.** Reminders take over the *deferred agent work* items. Items where we wait on *other people* stay as tracker rows, which the team can see. A reminder may point to a tracker row, but the row stays the source of truth.
9. **The plan must be self-contained.** The owning session may never be reopened, so the plan must be detailed enough for a fresh session to carry it out.
10. **Failures are loud.** If the plan file is missing when the reminder fires, the digest and the payload say `PLAN MISSING: <path>`; the reminder is never dropped. A reminder file that can't be parsed is reported by name. The hook always exits 0, so a broken reminder store never blocks a prompt, but it is never silent: on an unexpected error at `SessionStart` it prints `reminders hook error: <ExceptionType>`. A hook that crashes without saying anything would mean reminders never fire, which is the original problem. At `UserPromptSubmit` it stays quiet, so the error isn't repeated on every prompt.

11. **One home for plans without a project doc.** Before this rule each session picked its own durable folder (a profile dir, a routines log dir), so plans ended up scattered and were never cleaned up. Now `remind.py plan-path <id>` prints `<config dir>/reminders/plans/<id>.md` and creates the folder, and `done` moves that plan to `done/plans/` with its reminder. It is per profile, like the reminders that point to it. A plan that lives in a project doc is never moved or archived.

## Record

JSON, because the hook uses only the Python standard library, which has no YAML parser. Both scripts run on stock macOS `python3` (3.9), so no `@dataclass(slots=True)` (3.10+); a test runs them under `/usr/bin/python3` when it is 3.9.

```json
{
  "id": "figma-vardefs-after-reset",
  "title": "Fetch variable defs for the 16 component sets",
  "due": "2026-12-01T09:00",
  "session_id": "ce3b7695-...",
  "cwd": "/Users/<user>/Desktop/work/allswell-workspace",
  "plan": "/Users/<user>/Desktop/work/allswell-workspace/my-dev-things/designs/README.md#after-mcp-reset",
  "why": "Figma MCP monthly limit resets",
  "status": "pending",
  "delivered_to": [],
  "created": "2026-11-23T11:30"
}
```

- `due`: a date or a local datetime. A bare date means 09:00 that day. A UTC offset is rejected, because an aware datetime can't be compared with the others.
- `status`: `pending` or `done`. "Delivered" comes from `delivered_to` and isn't a separate status. `snooze` sets a new `due` and clears `delivered_to`.
- `done` moves the file to `<config dir>/reminders/done/`, and a plan in `<config dir>/reminders/plans/` to `done/plans/`. Nothing is deleted: a reused id is archived as `<id>.2.json` (`<id>.2.md`), `<id>.3.json`, and so on.
- Writes are atomic: the file is written to a temp file and renamed into place.

## Hook behaviour

| Event | Reminder due? | Session | Output |
|---|---|---|---|
| `SessionStart` | yes | any | digest lines + summary line |
| `SessionStart` / `UserPromptSubmit` | yes | owner, not yet in `delivered_to` | payload, then the session id is added to `delivered_to` |
| `UserPromptSubmit` | any | not the owner | nothing (keeps the hot path quiet) |
| `SessionStart` | none due, some scheduled | any | the summary line only |

`UserPromptSubmit` covers an owner session that is already open when the due date passes. It must stay fast: it lists one directory and parses small JSON files, and it never runs `when_cmd`.

Output goes to stdout with exit 0, which Claude Code adds to the session context for both events.

## Interfaces

- `/remind`: the skill a session invokes at the moment it writes a deferred plan. It fills in `session_id` and `cwd` from the session and asks only for `due`, `title` and `plan`. CLAUDE.md gets one line: "When a plan is blocked on a future date or event, register it with /remind." Without that line, using the skill depends on someone remembering, which is the original problem.
- `remind.py add | plan-path <id> | list | done <id> | snooze <id> <when>`: the CLI behind it. `plan-path` prints where to write a plan that no project doc holds. `list` shows every pending reminder, due ones marked `DUE`.
- **Permissions**: `settings.base.json` allows `python3 -I {{CONFIG_DIR}}/skills/remind/scripts/remind.py` with `plan-path`, `list`, `done` and `snooze`, so getting a plan path or closing a reminder doesn't stop on a prompt. `add` is deliberately not allowed: a reminder makes a session carry out a plan later, so creating one needs the user's approval. Without that, a session that read injected text could plant a reminder, with any plan file, in another session.
- **Validation**: the hook prints reminder fields into Claude's context, so `remind.validate` checks them on `add` and again on every load. `id` and `session_id` must be tokens (`[A-Za-z0-9_.-]`, not starting with `.`). Text fields must be one line, at most 300 characters, with no backticks. A file that fails is reported as unreadable and never printed.

## Verified during implementation (2026-11-23)

- **Resume keeps the session id.** Two sessions started with `claude --resume <id>` kept appending to `<id>.jsonl` with that `sessionId`. A fork gets a new id (`source: "fork"`), which is why the cwd fallback exists.
- **Hook input** ([hooks reference](https://code.claude.com/docs/en/hooks.md)): both events get `session_id`, `transcript_path`, `cwd`, `hook_event_name`. `SessionStart` also gets `source`: `startup`, `resume`, `clear`, `compact` or `fork`. The hook doesn't filter on `source`: the digest is useful after clearing the conversation and after compaction too.
- **Output**: plain stdout on exit 0 is added to context for both events. It is capped at 10,000 characters; past that, Claude only sees a 2,000-character preview. The hook keeps its output under 9,000 characters. A payload that doesn't fit stays undelivered and arrives with the next prompt. Digest lines that don't fit are counted (`...and N more`), not printed.
- **Transcripts are deleted after 30 days by default** (`cleanupPeriodDays`, [data usage](https://code.claude.com/docs/en/data-usage.md)). The "owner session gone" check looks for `<config>/projects/*/<session_id>.jsonl`; the owner's own `transcript_path` isn't in the hook input of another session.

## Later (not v1)

- **`when_cmd`**: an event check, run only after `due`, at `SessionStart` only, with a timeout.
- **`remind claim <id>`**: lets one session take over an orphaned reminder. Not needed while the user is the one resuming sessions. If it is added, it must be atomic: create `<id>.claim` with `O_CREAT|O_EXCL`, so when two sessions claim at the same moment, only one wins.
- **Push notification**: a launchd job that sends a macOS notification when something is due and no session is open.
