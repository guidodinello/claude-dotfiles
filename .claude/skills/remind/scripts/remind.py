#!/usr/bin/env python3
"""Reminders: a trigger plus a pointer to a plan doc, brought back to a session once due.

One JSON file per reminder in <config dir>/reminders/ (local to this machine, never
synced). The config dir is derived from this file's location (skills/remind/scripts/), so
each CLAUDE_CONFIG_DIR keeps its own reminders, next to the session transcripts they
point to. A plan that no project doc already holds goes in <config dir>/reminders/plans/,
and `done` archives it with its reminder. Spec: docs/reminders.md in claude-dotfiles.

CLI:
  remind.py add --title T --due WHEN --plan /abs/path[#anchor] --session-id ID
                [--cwd DIR] [--why W] [--id ID]
  remind.py plan-path ID
  remind.py list
  remind.py done ID
  remind.py snooze ID WHEN

WHEN is a date (2026-12-01, which means 09:00), a local datetime (2026-12-01T14:30), or a
duration from now (3h, 2d, 1w).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

# absolute(), not resolve(): sync.sh symlinks this file into the config dir, and the
# config dir is where the link lives, not the repo file it points to.
CONFIG_DIR = Path(__file__).absolute().parents[3]
STORE = CONFIG_DIR / "reminders"
DEFAULT_HOUR = 9
DURATION = re.compile(r"^(\d+)([hdw])$")
DURATION_UNITS = {"h": "hours", "d": "days", "w": "weeks"}
SCRIPT = Path(__file__).absolute()


# No slots=True: it needs Python 3.10, and the hook must load on stock macOS python3 (3.9).
@dataclass
class Reminder:
    id: str
    title: str
    due: str
    plan: str
    session_id: str
    cwd: str
    why: str = ""
    status: str = "pending"
    delivered_to: list[str] = field(default_factory=list)
    created: str = ""

    @property
    def due_at(self) -> datetime:
        return parse_when(self.due)

    def is_due(self, now: datetime) -> bool:
        return self.due_at <= now

    def plan_file(self) -> Path:
        return Path(self.plan.split("#", 1)[0])


# The hook prints these fields into Claude's context, so a newline or backtick in one
# could pass for an instruction. Ids are file names and resume arguments: tokens only.
TOKEN = re.compile(r"[A-Za-z0-9_.-]{1,80}")
UNSAFE_TEXT = re.compile(r"[\x00-\x1f\x7f`]")
MAX_TEXT = 300


def validate(reminder: Reminder) -> None:
    """Raise ValueError when a field could not be printed safely into context."""
    for name in ("id", "session_id"):
        if not TOKEN.fullmatch(getattr(reminder, name)) or getattr(reminder, name)[0] == ".":
            raise ValueError(f"{name} must match {TOKEN.pattern} and not start with '.'")
    if not all(isinstance(s, str) and TOKEN.fullmatch(s) for s in reminder.delivered_to):
        raise ValueError("delivered_to holds a malformed session id")
    for name in ("title", "why", "cwd", "plan", "due", "status", "created"):
        value = getattr(reminder, name)
        if not isinstance(value, str) or len(value) > MAX_TEXT or UNSAFE_TEXT.search(value):
            raise ValueError(f"{name} must be one line of at most {MAX_TEXT} chars, no backticks")
    reminder.due_at  # noqa: B018 - raises ValueError on a malformed date


def parse_when(text: str, now: datetime | None = None) -> datetime:
    """A date (09:00 that day), a local ISO datetime, or a duration from now."""
    text = text.strip()
    match = DURATION.match(text)
    if match:
        amount, unit = int(match.group(1)), DURATION_UNITS[match.group(2)]
        return (now or datetime.now()) + timedelta(**{unit: amount})
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.fromisoformat(text).replace(hour=DEFAULT_HOUR)
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is not None:
        # An aware datetime can't be compared with the naive now(): one would break every sort.
        raise ValueError(f"use local time without a UTC offset, got {text!r}")
    return moment


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "reminder"


def path_for(reminder_id: str, store: Path = STORE) -> Path:
    return store / f"{reminder_id}.json"


def check_id(reminder_id: str) -> None:
    if not TOKEN.fullmatch(reminder_id) or reminder_id.startswith("."):
        raise SystemExit(f"not a reminder id: {reminder_id!r}")


def plan_path_for(reminder_id: str, store: Path = STORE) -> Path:
    """Where a plan goes when no project doc already describes the work."""
    return store / "plans" / f"{reminder_id}.md"


def archive_path(directory: Path, stem: str, suffix: str) -> Path:
    """A free name in directory: an id can be reused once closed; never overwrite a record."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{stem}{suffix}"
    copy = 2
    while target.exists():
        target = directory / f"{stem}.{copy}{suffix}"
        copy += 1
    return target


def write(reminder: Reminder, store: Path = STORE) -> None:
    """Atomic: write a temp file in the same dir, then rename it into place."""
    store.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=store, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(asdict(reminder), f, indent=2)
            f.write("\n")
        os.replace(tmp, path_for(reminder.id, store))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_all(store: Path = STORE) -> tuple[list[Reminder], list[str]]:
    """(pending reminders sorted by due, names of files that are unparsable or fail validate)."""
    reminders: list[Reminder] = []
    broken: list[str] = []
    if not store.is_dir():
        return reminders, broken
    for path in sorted(store.glob("*.json")):
        try:
            reminder = Reminder(**json.loads(path.read_text(encoding="utf-8")))
            validate(reminder)
            if reminder.id != path.stem:  # write() would update another file
                raise ValueError(f"id {reminder.id!r} does not match {path.name}")
        except (OSError, ValueError, TypeError):
            broken.append(path.name)
            continue
        if reminder.status == "pending":
            reminders.append(reminder)
    reminders.sort(key=lambda r: r.due_at)
    return reminders, broken


def load(reminder_id: str, store: Path = STORE) -> Reminder:
    check_id(reminder_id)
    path = path_for(reminder_id, store)
    if not path.is_file():
        raise SystemExit(f"no reminder with id {reminder_id!r} in {store}")
    try:
        reminder = Reminder(**json.loads(path.read_text(encoding="utf-8")))
        validate(reminder)
    except (ValueError, TypeError) as error:
        raise SystemExit(f"unreadable reminder file {path.name}: {error}") from None
    # write() and done build paths from reminder.id, so it must be the file's own name.
    if reminder.id != reminder_id:
        raise SystemExit(f"{path.name} holds id {reminder.id!r}, not {reminder_id!r}")
    return reminder


def transcript_exists(session_id: str, config: Path = CONFIG_DIR) -> bool:
    """Claude Code deletes old transcripts (cleanupPeriodDays); a gone one can't be resumed."""
    return any((config / "projects").glob(f"*/{session_id}.jsonl"))


# --- CLI ------------------------------------------------------------------------------


def cmd_add(args: argparse.Namespace, store: Path) -> str:
    plan = args.plan
    if not Path(plan.split("#", 1)[0]).is_absolute():
        raise SystemExit(f"--plan must be an absolute path, got {plan!r}")
    if not Path(plan.split("#", 1)[0]).is_file():
        raise SystemExit(f"--plan file does not exist: {plan.split('#', 1)[0]}")
    reminder = Reminder(
        id=args.id or slug(args.title),
        title=args.title,
        due=stamp(parse_when(args.due)),
        plan=plan,
        session_id=args.session_id,
        cwd=str(Path(args.cwd or os.getcwd()).resolve()),
        why=args.why or "",
        created=stamp(datetime.now()),
    )
    validate(reminder)
    if path_for(reminder.id, store).exists():
        raise SystemExit(f"a reminder with id {reminder.id!r} already exists; pass --id")
    write(reminder, store)
    return f"added {reminder.id}, due {reminder.due}"


def cmd_plan_path(args: argparse.Namespace, store: Path) -> str:
    check_id(args.id)
    path = plan_path_for(args.id, store)
    if path_for(args.id, store).exists():
        raise SystemExit(f"a reminder with id {args.id!r} already exists; pick another id")
    # Another session may have written it and not yet run add (add always prompts).
    if path.exists():
        raise SystemExit(
            f"{path} already exists: if you wrote it, run add with --id {args.id};"
            " otherwise pick another id"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def cmd_list(_: argparse.Namespace, store: Path) -> str:
    reminders, broken = load_all(store)
    now = datetime.now()
    lines = [
        f"{'DUE ' if r.is_due(now) else '    '}{r.due}  {r.id}  {r.title}  ({r.cwd})"
        + ("  [delivered, not done]" if r.delivered_to else "")
        for r in reminders
    ]
    lines += [f"unreadable reminder file: {name}" for name in broken]
    return "\n".join(lines) or "no pending reminders"


def cmd_done(args: argparse.Namespace, store: Path) -> str:
    reminder = load(args.id, store)
    reminder.status = "done"
    write(reminder, store)
    record = archive_path(store / "done", reminder.id, ".json")
    os.replace(path_for(reminder.id, store), record)
    # Only this reminder's own plan (plans/<id>.*) is archived: a project doc, or a plan
    # another reminder points to, stays where it is.
    plan = reminder.plan_file()
    if not (
        plan.is_file()
        and plan.stem == reminder.id
        and plan.resolve().parent == (store / "plans").resolve()
    ):
        return f"done {reminder.id}"
    try:
        # Named after the archived record (<id>.2.json -> <id>.2.md), so the pair matches.
        os.replace(plan, archive_path(store / "done" / "plans", record.stem, plan.suffix))
    except OSError as error:
        return f"done {reminder.id} (plan not archived, still at {plan}: {error})"
    return f"done {reminder.id}"


def cmd_snooze(args: argparse.Namespace, store: Path) -> str:
    reminder = load(args.id, store)
    reminder.due = stamp(parse_when(args.when))
    reminder.delivered_to = []
    write(reminder, store)
    return f"snoozed {reminder.id} to {reminder.due}"


def main(argv: list[str] | None = None, store: Path = STORE) -> int:
    parser = argparse.ArgumentParser(prog="remind.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("--title", required=True)
    add.add_argument("--due", required=True)
    add.add_argument("--plan", required=True)
    add.add_argument("--session-id", required=True)
    add.add_argument("--cwd")
    add.add_argument("--why")
    add.add_argument("--id")
    plan_path = sub.add_parser("plan-path")
    plan_path.add_argument("id")
    sub.add_parser("list")
    done = sub.add_parser("done")
    done.add_argument("id")
    snooze = sub.add_parser("snooze")
    snooze.add_argument("id")
    snooze.add_argument("when")
    args = parser.parse_args(argv)
    handler = {"add": cmd_add, "plan-path": cmd_plan_path, "list": cmd_list, "done": cmd_done, "snooze": cmd_snooze}
    try:
        print(handler[args.command](args, store))
    except ValueError as error:
        raise SystemExit(f"invalid reminder: {error}") from None
    return 0


if __name__ == "__main__":
    sys.exit(main())
