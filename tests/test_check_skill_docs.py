"""Tests for .github/scripts/check-skill-docs.py, the gate for docs/skills.md.
The real script runs against a throwaway tree, because it reads cwd-relative
paths. Run: python3 -m unittest discover -s tests"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "check-skill-docs.py"

TABLE = "| Skill | Purpose |\n|---|---|\n| `/alpha` | first |\n| `/beta` | second |\n"


class CheckSkillDocsCase(unittest.TestCase):
    def setUp(self):
        self.tree = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tree)
        for name in ("alpha", "beta"):
            self.write(f".claude/skills/{name}/SKILL.md", f"---\nname: {name}\n---\n")
        self.write("docs/skills.md", TABLE)
        self.write("README.md", "Run `/alpha` or `/beta`.\n")
        self.write("CLAUDE.md", "No skill references here.\n")

    def write(self, relative: str, text: str) -> None:
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def check(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=self.tree, capture_output=True, text=True
        )

    def test_clean_tree_passes(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("checked 2 skills", result.stdout)
        self.assertIn("0 problem(s)", result.stdout)

    def test_skill_without_table_row_fails(self):
        self.write(".claude/skills/gamma/SKILL.md", "---\nname: gamma\n---\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("docs/skills.md: skill `gamma` has no table row", result.stdout)

    def test_row_without_skill_directory_fails(self):
        self.write("docs/skills.md", TABLE + "| `/delta` | gone |\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("docs/skills.md: row `/delta` has no skill directory", result.stdout)

    def test_duplicate_row_fails(self):
        self.write("docs/skills.md", TABLE + "| `/alpha` | again |\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("row `/alpha` appears more than once", result.stdout)

    def test_reference_to_missing_skill_fails_with_file_and_line(self):
        self.write("README.md", "Run `/alpha`.\nThen `/ghost`.\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("README.md:2: `/ghost` is not a skill", result.stdout)

    def test_reference_in_nested_doc_is_checked(self):
        self.write("docs/deep/page.md", "See `/ghost`.\n")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("docs/deep/page.md:1: `/ghost` is not a skill", result.stdout)

    def test_listed_non_skill_tokens_are_allowed(self):
        self.write("README.md", "Use `/compact`, `/mcp`, `/usage` and `/skill-name`.\n")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_skills_at_all_fails_closed(self):
        shutil.rmtree(self.tree / ".claude")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No skills found", result.stdout + result.stderr)

    def test_table_without_rows_fails_closed(self):
        self.write("docs/skills.md", "No table here.\n")
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No skill table rows found", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
