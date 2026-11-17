"""Tests for .claude/hooks/guard-env-files.sh. Run: python3 -m unittest discover -s tests

Every file here is fake: names only, empty contents, in a throwaway directory."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "guard-env-files.sh"

BLOCK = 2
ALLOW = 0

# (expected exit code, basename). Judged wherever the file sits.
NAMES = [
    (BLOCK, ".env"),
    (BLOCK, ".env.local"),
    (BLOCK, ".env.development.local"),
    (BLOCK, ".env.backup"),
    (BLOCK, ".env.prod"),
    (BLOCK, ".envrc"),
    (BLOCK, "prod.env"),
    (BLOCK, ".ENV"),
    (BLOCK, ".Env.Backup"),
    (ALLOW, ".env.example"),
    (ALLOW, ".env.prod.example"),
    (ALLOW, ".env.sample"),
    (ALLOW, ".env.template"),
    (ALLOW, ".ENV.EXAMPLE"),
    (ALLOW, "environment.ts"),
    (ALLOW, "env.py"),
    (ALLOW, "README.md"),
]


def run_guard(stdin: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(GUARD)], input=stdin, capture_output=True, text=True, timeout=30)


def hook_input(tool: str, **tool_input) -> str:
    return json.dumps({"tool_name": tool, "tool_input": tool_input})


class GuardEnvFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_file_tools_judge_the_basename(self):
        for tool in ("Read", "Edit", "Write"):
            for want, name in NAMES:
                with self.subTest(tool=tool, name=name):
                    path = str(self.tmp / "nested" / name)  # does not exist: the name decides
                    self.assertEqual(run_guard(hook_input(tool, file_path=path)).returncode, want)

    def test_relative_and_absolute_paths(self):
        for path, want in (
            (".env.backup", BLOCK),
            ("./a/b/.env", BLOCK),
            ("/private/tmp/x/.env.staging", BLOCK),
            ("/private/tmp/x/.env.example", ALLOW),
            ("../.env.sample", ALLOW),
        ):
            with self.subTest(path=path):
                self.assertEqual(run_guard(hook_input("Read", file_path=path)).returncode, want)

    def test_notebook_edit_uses_notebook_path(self):
        self.assertEqual(run_guard(hook_input("NotebookEdit", notebook_path="/x/.env")).returncode, BLOCK)
        self.assertEqual(run_guard(hook_input("NotebookEdit", notebook_path="/x/a.ipynb")).returncode, ALLOW)

    def test_symlink_to_an_env_file_is_blocked(self):
        real = self.tmp / ".env.backup"
        real.write_text("")
        link = self.tmp / "notes"
        link.symlink_to(real)
        chained = self.tmp / "more-notes"
        chained.symlink_to(link)
        for path in (link, chained):
            with self.subTest(path=path.name):
                self.assertEqual(run_guard(hook_input("Read", file_path=str(path))).returncode, BLOCK)

    def test_symlink_to_an_example_is_allowed(self):
        real = self.tmp / ".env.example"
        real.write_text("")
        link = self.tmp / "notes"
        link.symlink_to(real.name)  # relative target
        self.assertEqual(run_guard(hook_input("Read", file_path=str(link))).returncode, ALLOW)

    def test_grep_blocks_an_env_file_path(self):
        for name in (".env", ".env.backup", "prod.env"):
            with self.subTest(name=name):
                result = run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / name)))
                self.assertEqual(result.returncode, BLOCK)

    def test_grep_allows_examples_directories_and_no_path(self):
        (self.tmp / ".env.d").mkdir()
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / ".env.example"))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=str(self.tmp / ".env.d"))).returncode, ALLOW)
        self.assertEqual(run_guard(hook_input("Grep", pattern="x")).returncode, ALLOW)

    def test_grep_with_a_path_that_is_not_a_string_fails_closed(self):
        for path in (1, ["a"], {"a": 1}, True):
            with self.subTest(path=path):
                self.assertEqual(run_guard(hook_input("Grep", pattern="x", path=path)).returncode, BLOCK)

    def test_unreadable_input_fails_closed(self):
        for stdin in (
            "",
            "not json",
            "{}",
            '{"tool_name": 1}',
            '{"tool_name": "Read"}',
            '{"tool_name": "Read", "tool_input": {}}',
            '{"tool_name": "Read", "tool_input": {"file_path": ""}}',
            '{"tool_name": "Read", "tool_input": {"file_path": 7}}',
            '{"tool_name": "Edit", "tool_input": {"path": "/x/a.txt"}}',
        ):
            with self.subTest(stdin=stdin):
                self.assertEqual(run_guard(stdin).returncode, BLOCK)

    def test_block_message_goes_to_stderr(self):
        result = run_guard(hook_input("Read", file_path="/x/.env.backup"))
        self.assertIn("BLOCKED", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
