#!/usr/bin/env python3
"""SessionStart / UserPromptSubmit hook: bring back reminders that are due.

Reminders live in <config dir>/reminders/ and are written by the remind skill's
remind.py, which this hook imports (the way dev-docs-index-check.py reuses check_index.py).
Spec: docs/reminders.md.

SessionStart prints, as context for Claude (plain stdout on exit 0):
  - `session_id: <id> (remind command: python3 -I <abs path>/remind.py)`, so the remind
    skill can record which session owns a reminder, and run the exact command the
    settings allow rule matches (a `~/` spelling would not match it);
  - the payload for each due reminder this session owns and has not been given yet;
  - a digest line for every other due reminder, with no plan content, so no other
    session takes the work on by accident;
  - `Reminders: N scheduled, next: <date>` for those not yet due.
UserPromptSubmit prints only the payload, for an owner session that was already open
when the reminder came due. It stays quiet otherwise, since it runs on every prompt.

It never blocks a prompt (always exit 0), but it is never silent about a failure either:
a missing plan file or an unreadable reminder file is named in the output, and an
unexpected error at SessionStart prints `reminders hook error: <type>`. A hook that died
quietly would mean reminders never fire, which is the problem it exists to solve.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from remind import Reminder  # ty: ignore[unresolved-import]

# absolute(), not resolve(): keep the symlinked config-dir path (see remind.CONFIG_DIR).
SCRIPTS = Path(__file__).absolute().parent.parent / "skills" / "remind" / "scripts"
# Plain stdout is capped at 10,000 characters; past that Claude sees only a 2,000-character
# preview. Stay under it with room to spare. A payload that doesn't fit stays undelivered
# and arrives with the next prompt; digest lines that don't fit are counted, not printed.
MAX_CHARS = 9_000


class Output:
    """Lines of hook output that never exceed MAX_CHARS in total."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.size = 0

    def add(self, line: str) -> bool:
        if self.size + len(line) + 1 > MAX_CHARS:
            return False
        self.lines.append(line)
        self.size += len(line) + 1
        return True


def payload(reminder: Reminder, script: Path) -> str:
    lines = [f"Reminder `{reminder.id}` is due: {reminder.title}."]
    if reminder.why:
        lines.append(f"Why it waited: {reminder.why}.")
    if reminder.plan_file().is_file():
        lines.append(f"Read {reminder.plan} and carry out the plan.")
    else:
        lines.append(f"PLAN MISSING: {reminder.plan} does not exist. Tell the user.")
    lines.append(
        f"When it is finished, close it with `python3 -I {script} done {reminder.id}`, "
        f"or postpone it with `python3 -I {script} snooze {reminder.id} <2d|YYYY-MM-DD>`."
    )
    return "\n".join(lines)


def digest_line(reminder: Reminder, session_id: str, cwd: str, remind: ModuleType) -> str:
    if reminder.session_id == session_id:
        where = "this session"
    elif remind.transcript_exists(reminder.session_id):
        where = f"resume with `claude --resume {reminder.session_id}`"
    else:
        where = f"owner session gone: start fresh in {reminder.cwd}"
    notes = []
    if reminder.cwd == cwd and reminder.session_id != session_id:
        notes.append("same project")
    if reminder.delivered_to:
        notes.append("delivered, not done")
    if not reminder.plan_file().is_file():
        notes.append(f"PLAN MISSING: {reminder.plan}")
    suffix = f" [{'; '.join(notes)}]" if notes else ""
    return (
        f"- `{reminder.id}` {reminder.title} (due {reminder.due}, {reminder.cwd}): {where}{suffix}"
    )


def run(data: dict[str, Any], remind: ModuleType) -> list[str]:
    event = data.get("hook_event_name")
    session_id = data.get("session_id") or ""
    cwd = str(Path(data.get("cwd") or ".").resolve())
    reminders, broken = remind.load_all()
    now = datetime.now()
    due = [r for r in reminders if r.is_due(now)]

    out = Output()
    if event == "SessionStart":
        out.add(f"session_id: {session_id} (remind command: python3 -I {remind.SCRIPT})")
    delivered_now: set[str] = set()
    for reminder in due:
        if reminder.session_id != session_id or session_id in reminder.delivered_to:
            continue
        if not out.add(payload(reminder, remind.SCRIPT)):
            continue  # stays undelivered, so the next prompt brings it
        reminder.delivered_to.append(session_id)
        remind.write(reminder)
        delivered_now.add(reminder.id)
    if event != "SessionStart":
        return out.lines

    # A reminder this session just received in full needs no digest line as well.
    digest = [r for r in due if r.id not in delivered_now]
    if digest:
        out.add("Reminders due (awareness only; the owning session does the work):")
        shown = 0
        for reminder in digest:
            if not out.add(digest_line(reminder, session_id, cwd, remind)):
                break
            shown += 1
        if shown < len(digest):
            out.lines.append(f"- ...and {len(digest) - shown} more (remind.py list)")
    later = [r for r in reminders if not r.is_due(now)]
    if later:
        out.add(f"Reminders: {len(later)} scheduled, next: {later[0].due}")
    for name in broken:
        if not out.add(f"Unreadable reminder file: {name}"):
            out.lines.append("More unreadable reminder files (remind.py list)")
            break
    return out.lines


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(data, dict):
        return 0
    try:
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(SCRIPTS))
        import remind  # ty: ignore[unresolved-import]

        lines = run(data, remind)
    except Exception as error:  # never block a prompt, but never fail silently
        if data.get("hook_event_name") == "SessionStart":
            print(f"reminders hook error: {type(error).__name__}")
        return 0
    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
