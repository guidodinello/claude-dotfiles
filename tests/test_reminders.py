"""Tests for .claude/hooks/reminders.py and the remind skill's remind.py CLI.
Run: python3 -m unittest discover -s tests

Builds a throwaway config dir that mirrors the synced layout: hooks/ next to skills/, each
file a symlink into the repo, the way sync.sh links them into ~/.claude. The symlinks
matter: both scripts must derive <config>/reminders and <config>/projects from the linked
path, not from the repo file the link points to."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "reminders.py"
REMIND = REPO / ".claude" / "skills" / "remind" / "scripts" / "remind.py"

OWNER = "owner-session"
OTHER = "other-session"


class ReminderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.config = base / "config"
        (self.config / "hooks").mkdir(parents=True)
        scripts = self.config / "skills" / "remind" / "scripts"
        scripts.mkdir(parents=True)
        (self.config / "hooks" / HOOK.name).symlink_to(HOOK)
        (scripts / REMIND.name).symlink_to(REMIND)
        self.hook = self.config / "hooks" / HOOK.name
        self.remind_script = scripts / REMIND.name
        self.store = self.config / "reminders"
        self.project = base / "project"
        self.project.mkdir()
        self.plan = self.project / "plan.md"
        self.plan.write_text("# Plan\n\n## After reset\n\nDo the thing.\n")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def remind(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", str(self.remind_script), *args],
            capture_output=True,
            text=True,
            cwd=self.project,
        )

    def add(self, due: str, *, rid: str = "r1", session: str = OWNER, plan: Path | None = None):
        result = self.remind(
            "add",
            "--title", "Fetch variable defs",
            "--due", due,
            "--plan", f"{plan or self.plan}#after-reset",
            "--session-id", session,
            "--id", rid,
            "--why", "limit resets",
        )  # fmt: skip
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def stored(self, rid: str = "r1") -> dict:
        return json.loads((self.store / f"{rid}.json").read_text())

    def hook_run(self, event: str, session: str, cwd: Path | None = None) -> str:
        payload = {"hook_event_name": event, "session_id": session, "cwd": str(cwd or self.project)}
        result = subprocess.run(
            [sys.executable, "-I", str(self.hook)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def make_transcript(self, session: str) -> None:
        folder = self.config / "projects" / "-some-project"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{session}.jsonl").write_text("{}\n")


class HookDeliveryTest(ReminderTestCase):
    def test_owner_gets_the_payload_once_at_session_start(self) -> None:
        self.add("1h")
        (self.store / "r1.json").write_text(
            json.dumps({**self.stored(), "due": "2000-01-01T09:00"})
        )

        first = self.hook_run("SessionStart", OWNER)
        self.assertIn("Reminder `r1` is due", first)
        self.assertIn(f"Read {self.plan}#after-reset", first)
        self.assertIn(f"python3 -I {self.remind_script} done r1", first)
        self.assertEqual(self.stored()["delivered_to"], [OWNER])

        second = self.hook_run("SessionStart", OWNER)
        self.assertNotIn("Reminder `r1` is due", second)
        self.assertIn("delivered, not done", second)

    def test_owner_already_open_gets_it_on_the_next_prompt_only_once(self) -> None:
        self.add("2000-01-01")
        self.assertIn("Reminder `r1` is due", self.hook_run("UserPromptSubmit", OWNER))
        self.assertEqual(self.hook_run("UserPromptSubmit", OWNER), "")

    def test_other_sessions_get_a_digest_line_without_the_plan(self) -> None:
        self.add("2000-01-01")
        self.make_transcript(OWNER)

        out = self.hook_run("SessionStart", OTHER)

        self.assertIn(f"claude --resume {OWNER}", out)
        self.assertIn("same project", out)
        self.assertNotIn("Read ", out)
        self.assertEqual(self.stored()["delivered_to"], [])

    def test_digest_says_when_the_owner_transcript_is_gone(self) -> None:
        self.add("2000-01-01")
        out = self.hook_run("SessionStart", OTHER, cwd=Path(self._tmp.name))
        self.assertIn(f"owner session gone: start fresh in {self.project.resolve()}", out)
        self.assertNotIn("same project", out)

    def test_prompts_in_other_sessions_stay_quiet(self) -> None:
        self.add("2000-01-01")
        self.assertEqual(self.hook_run("UserPromptSubmit", OTHER), "")

    def test_reminders_not_yet_due_only_show_as_a_count(self) -> None:
        self.add("2d", rid="later")
        self.add("1w", rid="much-later")

        out = self.hook_run("SessionStart", OWNER)

        self.assertIn("Reminders: 2 scheduled, next: ", out)
        self.assertNotIn("Reminders due", out)
        self.assertNotIn("Reminder `later` is due", out)

    def test_session_start_always_names_the_session_and_command(self) -> None:
        out = self.hook_run("SessionStart", OWNER)
        self.assertEqual(
            out.strip(),
            f"session_id: {OWNER} (remind command: python3 -I {self.remind_script})",
        )

    def test_a_missing_plan_file_is_reported_not_dropped(self) -> None:
        self.add("2000-01-01")
        self.plan.unlink()

        self.assertIn("PLAN MISSING", self.hook_run("SessionStart", OTHER))
        self.assertIn("PLAN MISSING", self.hook_run("UserPromptSubmit", OWNER))

    def test_an_unreadable_reminder_file_is_named(self) -> None:
        self.store.mkdir()
        (self.store / "broken.json").write_text("{not json")
        self.assertIn("Unreadable reminder file: broken.json", self.hook_run("SessionStart", OWNER))

    def test_an_unexpected_error_is_reported_at_session_start_and_never_blocks(self) -> None:
        self.remind_script.unlink()
        self.assertIn(
            "reminders hook error: ModuleNotFoundError", self.hook_run("SessionStart", OWNER)
        )
        self.assertEqual(self.hook_run("UserPromptSubmit", OWNER), "")

    def test_bad_stdin_exits_cleanly(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", str(self.hook)], input="nope", capture_output=True, text=True
        )
        self.assertEqual((result.returncode, result.stdout), (0, ""))


class RemindCliTest(ReminderTestCase):
    def test_add_stores_a_pointer_with_the_session_and_cwd(self) -> None:
        self.add("2026-12-01")
        record = self.stored()
        self.assertEqual(record["due"], "2026-12-01T09:00")
        self.assertEqual(record["plan"], f"{self.plan}#after-reset")
        self.assertEqual(record["session_id"], OWNER)
        self.assertEqual(record["cwd"], str(self.project.resolve()))
        self.assertEqual(record["status"], "pending")

    def test_add_refuses_a_relative_or_missing_plan(self) -> None:
        relative = self.remind(
            "add", "--title", "t", "--due", "1d", "--plan", "plan.md", "--session-id", OWNER
        )
        self.assertIn("absolute path", relative.stderr)
        missing = self.remind(
            "add", "--title", "t", "--due", "1d",
            "--plan", str(self.project / "nope.md"), "--session-id", OWNER,
        )  # fmt: skip
        self.assertIn("does not exist", missing.stderr)
        self.assertFalse(self.store.exists())

    def test_add_refuses_a_duplicate_id(self) -> None:
        self.add("1d")
        again = self.remind(
            "add", "--title", "t", "--due", "1d", "--plan", str(self.plan),
            "--session-id", OWNER, "--id", "r1",
        )  # fmt: skip
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", again.stderr)

    def test_add_rejects_a_bad_date(self) -> None:
        bad = self.remind(
            "add", "--title", "t", "--due", "next tuesday", "--plan", str(self.plan),
            "--session-id", OWNER,
        )  # fmt: skip
        self.assertIn("bad date or duration", bad.stderr)

    def test_durations_count_from_now(self) -> None:
        self.add("2d")
        due = datetime.fromisoformat(self.stored()["due"])
        self.assertAlmostEqual(
            (due - datetime.now()).total_seconds(), timedelta(days=2).total_seconds(), delta=120
        )

    def test_done_moves_the_file_out_of_the_pending_store(self) -> None:
        self.add("2000-01-01")
        self.assertEqual(self.remind("done", "r1").returncode, 0)

        self.assertFalse((self.store / "r1.json").exists())
        done = json.loads((self.store / "done" / "r1.json").read_text())
        self.assertEqual(done["status"], "done")
        self.assertNotIn("r1", self.hook_run("SessionStart", OTHER).replace(OTHER, ""))

    def test_snooze_moves_the_date_and_redelivers(self) -> None:
        self.add("2000-01-01")
        self.hook_run("SessionStart", OWNER)
        self.assertEqual(self.remind("snooze", "r1", "2026-12-24").returncode, 0)

        record = self.stored()
        self.assertEqual((record["due"], record["delivered_to"]), ("2026-12-24T09:00", []))

    def test_list_marks_due_reminders(self) -> None:
        self.add("2000-01-01", rid="past")
        self.add("2d", rid="future")
        lines = self.remind("list").stdout.splitlines()
        self.assertTrue(lines[0].startswith("DUE ") and "past" in lines[0])
        self.assertTrue(lines[1].startswith("    ") and "future" in lines[1])

    def test_unknown_id_fails(self) -> None:
        result = self.remind("done", "ghost")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no reminder with id 'ghost'", result.stderr)


if __name__ == "__main__":
    unittest.main()
