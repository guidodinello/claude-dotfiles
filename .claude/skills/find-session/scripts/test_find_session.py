"""Unit tests for find_session.py config-dir handling. Run: python3 -m unittest test_find_session."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_session as fs  # ty: ignore[unresolved-import]


class ConfigDirTest(unittest.TestCase):
    def test_flag_beats_env(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": "/env"}):
            self.assertEqual(fs.projects_dirs("/flag"), [Path("/flag/projects")])
            self.assertEqual(fs.projects_dirs(None), [Path("/env/projects")])

    def test_defaults_search_both_existing_dirs(self):
        import tempfile

        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {"HOME": home}):
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
            self.assertEqual(fs.projects_dirs(None), [])
            Path(home, ".claude/projects").mkdir(parents=True)
            Path(home, ".claude-work/projects").mkdir(parents=True)
            self.assertEqual(
                [p.parent.name for p in fs.projects_dirs(None)], [".claude", ".claude-work"]
            )

    def test_resume_prefix_only_for_non_default_dir(self):
        home = Path.home()
        self.assertEqual(fs.resume_prefix(home / ".claude/projects/p/s.jsonl"), "")
        self.assertEqual(
            fs.resume_prefix(home / ".claude-work/projects/p/s.jsonl"),
            f"CLAUDE_CONFIG_DIR={home}/.claude-work ",
        )


if __name__ == "__main__":
    unittest.main()
