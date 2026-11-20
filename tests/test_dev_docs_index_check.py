"""Tests for .claude/hooks/dev-docs-index-check.py. Run: python3 -m unittest discover -s tests

Builds a throwaway config dir that mirrors the synced layout (hooks/ next to skills/), so
the hook finds check_index.py the way it does under ~/.claude."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "dev-docs-index-check.py"
CHECKER = REPO / ".claude" / "skills" / "dev-docs-index" / "scripts" / "check_index.py"

BLOCK = 2
ALLOW = 0


class StopHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        config = base / "config"
        (config / "hooks").mkdir(parents=True)
        (config / "skills" / "dev-docs-index" / "scripts").mkdir(parents=True)
        shutil.copy(HOOK, config / "hooks" / HOOK.name)
        shutil.copy(CHECKER, config / "skills" / "dev-docs-index" / "scripts" / CHECKER.name)
        self.hook = config / "hooks" / HOOK.name
        self.project = base / "project"
        self.tree = self.project / "my-dev-things"
        self.tree.mkdir(parents=True)
        (self.tree / "README.md").write_text("index")
        self.transcript = base / "transcript.jsonl"
        self.started = time.time() - 60
        self.write_transcript_entry(self.started)
        self.old_files()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_transcript_entry(self, epoch: float) -> None:
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(epoch))
        with self.transcript.open("a") as f:
            f.write(json.dumps({"type": "permission-mode"}) + "\n")
            f.write(json.dumps({"type": "user", "timestamp": stamp}) + "\n")

    def old_files(self) -> None:
        """Backdate everything so only files written after this count as changed."""
        past = time.time() - 7200
        for p in self.tree.rglob("*"):
            os.utime(p, (past, past))
        os.utime(self.tree / "README.md", (past, past))

    def run_hook(self, payload: object | str) -> subprocess.CompletedProcess:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            ["python3", "-I", str(self.hook)], input=stdin, capture_output=True, text=True,
            timeout=30,
        )

    def payload(self, **extra: object) -> dict:
        return {"cwd": str(self.project), "transcript_path": str(self.transcript),
                "stop_hook_active": False, **extra}

    def test_blocks_when_a_new_doc_is_not_indexed(self) -> None:
        (self.tree / "new-notes.md").write_text("x")
        result = self.run_hook(self.payload())
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("does not name new-notes.md", result.stderr)

    def test_allows_when_indexed(self) -> None:
        (self.tree / "new-notes.md").write_text("x")
        (self.tree / "README.md").write_text("`new-notes.md`")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_old_gaps_do_not_block_an_unrelated_session(self) -> None:
        (self.tree / "old-notes.md").write_text("x")
        self.old_files()
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_rewritten_logs_do_not_count_as_a_change(self) -> None:
        (self.tree / "old").mkdir()
        (self.tree / "old" / "notes.md").write_text("x")
        self.old_files()
        (self.tree / "logs").mkdir()
        (self.tree / "logs" / "ngrok.log").write_text("rewritten by a running stack")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_old_gap_in_another_folder_does_not_block(self) -> None:
        (self.tree / "README.md").write_text("`a/` `b/`")
        for name in ("a", "b"):
            (self.tree / name).mkdir()
            (self.tree / name / "README.md").write_text("`doc.md`")
            (self.tree / name / "doc.md").write_text("x")
        (self.tree / "b" / "stale.md").write_text("never indexed")
        self.old_files()
        (self.tree / "a" / "doc.md").write_text("edited this session")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_old_gap_in_a_parent_does_not_block_a_child_edit(self) -> None:
        (self.tree / "README.md").write_text("`a/`")
        (self.tree / "a").mkdir()
        (self.tree / "a" / "README.md").write_text("`doc.md`")
        (self.tree / "a" / "doc.md").write_text("x")
        (self.tree / "stale.md").write_text("never indexed")
        self.old_files()
        (self.tree / "a" / "doc.md").write_text("edited this session")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_new_folder_reports_its_parent_too(self) -> None:
        (self.tree / "inv").mkdir()
        (self.tree / "inv" / "report.md").write_text("x")
        result = self.run_hook(self.payload())
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("inv: no README.md", result.stderr)
        self.assertIn("does not name subfolder inv/", result.stderr)

    def test_transcript_written_after_the_edit_still_blocks(self) -> None:
        """The Linux case: the transcript's ctime/mtime is newer than every edit."""
        (self.tree / "new-notes.md").write_text("x")
        self.write_transcript_entry(time.time())
        result = self.run_hook(self.payload())
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("does not name new-notes.md", result.stderr)

    def test_unreadable_transcript_fails_open(self) -> None:
        (self.tree / "new-notes.md").write_text("x")
        self.transcript.write_text("no timestamps here\n")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)
        self.assertEqual(self.run_hook(self.payload(transcript_path=None)).returncode, ALLOW)

    def test_old_missing_readme_on_the_path_blocks(self) -> None:
        """Documented: without the parent README the new doc is unreachable."""
        (self.tree / "a" / "b").mkdir(parents=True)
        self.old_files()
        (self.tree / "a" / "b" / "README.md").write_text("`d.md`")
        (self.tree / "a" / "b" / "d.md").write_text("x")
        result = self.run_hook(self.payload())
        self.assertEqual(result.returncode, BLOCK)
        self.assertIn("a: no README.md", result.stderr)

    def test_non_string_cwd_fails_open(self) -> None:
        self.assertEqual(self.run_hook(self.payload(cwd=42)).returncode, ALLOW)

    def test_stop_hook_active_never_blocks(self) -> None:
        (self.tree / "new-notes.md").write_text("x")
        self.assertEqual(self.run_hook(self.payload(stop_hook_active=True)).returncode, ALLOW)

    def test_no_my_dev_things_folder(self) -> None:
        shutil.rmtree(self.tree)
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)

    def test_fails_open_on_bad_input(self) -> None:
        self.assertEqual(self.run_hook("not json").returncode, ALLOW)
        self.assertEqual(self.run_hook("[]").returncode, ALLOW)

    def test_fails_open_without_the_checker(self) -> None:
        (self.tree / "new-notes.md").write_text("x")
        shutil.rmtree(self.hook.parent.parent / "skills")
        self.assertEqual(self.run_hook(self.payload()).returncode, ALLOW)


if __name__ == "__main__":
    unittest.main()
