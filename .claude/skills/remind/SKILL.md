---
name: remind
description: "Trigger: remind me, after X happens do Y, blocked until a date, deferred plan, come back to this later, pending after the reset, list reminders, what's scheduled. Register a deferred plan as a reminder that comes back to this session once due, or list, close and snooze reminders."
---

# Reminders

A reminder brings a deferred plan back to the session that wrote it, once a date passes.
The `reminders.py` hook does the delivery at `SessionStart` and `UserPromptSubmit`. No
daemon is involved, so a date that passed while the laptop was off fires at the next
session or prompt. Spec: `docs/reminders.md` in claude-dotfiles.

A reminder is only a **trigger plus a pointer**. The plan lives in its own doc and is
never copied into the reminder.

## When to register one

Register a reminder when a plan is blocked on a **future date**, for example "after the
Figma MCP limit resets on Dec 1". If it's blocked on an event, such as a PR merging,
estimate a date to check it.

Don't register one when the wait is on **other people**, such as a review or a decision.
That belongs in the team's tracker, which everyone can see. A reminder may point to a
tracker row, but the row stays the source of truth.

## Adding a reminder

1. **Write the plan first, self-contained.** The owning session may never be reopened,
   so a fresh session must be able to carry the plan out from the doc alone. Include ids,
   commands and the order of steps. Give the plan a heading so the pointer can use an
   `#anchor`. Where it goes:
   - If a project doc already describes the work (a README, a `my-dev-things/` doc), add
     the plan there and point to it. That doc stays the only source of truth.
   - Otherwise, never pick a folder yourself. Pick the reminder id first, then get the path
     with `REMIND plan-path <id>` (see step 3 for `REMIND`). It prints
     `<config dir>/reminders/plans/<id>.md` and creates the folder. Write the plan there and
     pass the same `--id` to `add`. `done` archives that plan along with the reminder.
2. **Get this session's id and the remind command.** At the top of the session's context,
   the hook prints `session_id: <id> (remind command: python3 -I /abs/.../remind.py)`.
   If you can't see that line (for example, after compaction), ask the user for the id
   instead of guessing. A wrong id means the reminder never reaches this session.
3. **Run it with the remind command exactly as printed.** It uses an absolute path, which
   is the string the settings allow rules match. Below, `REMIND` stands for that command.
   `list`, `done` and `snooze` run without a prompt. `add` always asks the user, on
   purpose: a reminder tells a session to carry out a plan later, so only the user may
   create one (otherwise a session that read injected text could plant work in another
   session).

   ```bash
   REMIND add \
     --title "Fetch variable defs for the 16 component sets" \
     --due 2026-12-01 \
     --plan /abs/path/to/plan.md#after-mcp-reset \
     --session-id <id> \
     --why "Figma MCP monthly limit resets"
   ```

   `--due` takes a date (meaning 09:00 that day), `YYYY-MM-DDTHH:MM`, or a duration
   (`3h`, `2d`, `1w`). `--plan` must be an absolute path to an existing file. `--cwd`
   defaults to the current directory, and `--id` defaults to a slug of the title.
4. Tell the user the id and the due date in one line.

## When a reminder is due

The owning session gets a message telling it to read the plan and carry it out. When the
work is done, close the reminder:

```bash
REMIND done <id>
```

The due message prints the full command to use.

If the plan is still blocked, postpone it instead with `snooze <id> 2d` (or a date).
A reminder that was delivered but not closed stays in every session's digest marked
`delivered, not done`.

Other sessions only see a digest line with the resume command. Don't act on a digest
line from another session unless the user asks you to.

## Listing

```bash
REMIND list
```

The output shows every pending reminder, sorted by due date. Reminders that are already
due are marked `DUE`.
