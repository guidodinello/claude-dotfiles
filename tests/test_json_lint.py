"""Tests for .claude/hooks/json-lint.sh. Run: python3 -m unittest discover -s tests"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "json-lint.sh"

WARN = 2
QUIET = 0


class JsonLintTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def lint(self, rel: str, content: str | None) -> subprocess.CompletedProcess:
        path = self.dir / rel
        if content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        stdin = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
        return subprocess.run(["bash", str(HOOK)], input=stdin, capture_output=True, text=True)

    def test_valid_json_is_quiet(self):
        result = self.lint("a.json", '{"a": 1}')
        self.assertEqual((result.returncode, result.stderr), (QUIET, ""))

    def test_invalid_json_warns_on_stderr(self):
        result = self.lint("a.json", '{"a": 1,}')
        self.assertEqual(result.returncode, WARN)
        self.assertIn("a.json is not valid JSON", result.stderr)

    def test_other_files_are_ignored(self):
        self.assertEqual(self.lint("a.txt", "{ nope").returncode, QUIET)

    def test_json_with_comments_files_are_skipped(self):
        jsonc = '{ // comment\n"a": 1 }'
        for rel in ("tsconfig.json", "tsconfig.app.json", "jsconfig.json", ".vscode/settings.json", "devcontainer.json"):
            with self.subTest(rel=rel):
                self.assertEqual(self.lint(rel, jsonc).returncode, QUIET)

    def test_missing_file_is_quiet(self):
        self.assertEqual(self.lint("gone.json", None).returncode, QUIET)

    def test_unreadable_input_is_quiet(self):
        for stdin in ("not json", "{}"):
            with self.subTest(stdin=stdin):
                result = subprocess.run(["bash", str(HOOK)], input=stdin, capture_output=True, text=True)
                self.assertEqual(result.returncode, QUIET)


if __name__ == "__main__":
    unittest.main()
