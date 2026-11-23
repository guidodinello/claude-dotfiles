"""Tests for project-init, which writes .claude/settings.json into other repos.
Runs a throwaway copy of the script and its templates against throwaway
projects. Run: python3 -m unittest discover -s tests"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates" / "claude-settings"


@unittest.skipUnless(shutil.which("jq"), "project-init needs jq to merge")
class ProjectInitCase(unittest.TestCase):
    def setUp(self):
        # realpath: /tmp is a symlink on macOS and the script resolves paths.
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tmp)
        self.tool = tmp / "tool"
        self.project = tmp / "project"
        self.home = tmp / "home"
        for path in (self.tool, self.project, self.home):
            path.mkdir()
        shutil.copy2(REPO / "project-init", self.tool / "project-init")
        shutil.copytree(TEMPLATES, self.tool / "templates" / "claude-settings")

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        # The throwaway project sits outside any git repo, so the script falls
        # back to the directory it was given.
        env = {**os.environ, "HOME": str(self.home)}
        return subprocess.run(
            ["bash", str(self.tool / "project-init"), str(self.project), *args],
            capture_output=True, text=True, env=env,
        )

    def template(self, stack: str) -> dict:
        return json.loads((TEMPLATES / f"{stack}.json").read_text())

    def settings(self, name: str = "settings.json") -> dict:
        return json.loads((self.project / ".claude" / name).read_text())

    def write_settings(self, data: dict, name: str = "settings.json") -> Path:
        path = self.project / ".claude" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
        return path

    # -- fresh project ---------------------------------------------------------

    def test_fresh_project_gets_the_template_verbatim(self):
        result = self.run_script("python")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Wrote", result.stdout)
        target = self.project / ".claude" / "settings.json"
        self.assertEqual(target.read_bytes(), (TEMPLATES / "python.json").read_bytes())

    def test_every_template_scaffolds_with_an_explicit_stack(self):
        for stack in ("python", "php", "node"):
            with self.subTest(stack=stack):
                shutil.rmtree(self.project / ".claude", ignore_errors=True)
                result = self.run_script(stack)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(self.settings(), self.template(stack))

    # -- stack detection -------------------------------------------------------

    def test_stack_is_detected_from_marker_files(self):
        cases = {
            "pyproject.toml": "python",
            "requirements.txt": "python",
            "composer.json": "php",
            "package.json": "node",
        }
        for marker, stack in cases.items():
            with self.subTest(marker=marker):
                shutil.rmtree(self.project)
                self.project.mkdir()
                (self.project / marker).write_text("")
                result = self.run_script()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"Detected stack: {stack}", result.stdout)
                self.assertEqual(self.settings(), self.template(stack))

    def test_python_markers_win_over_node(self):
        (self.project / "package.json").write_text("{}")
        (self.project / "pyproject.toml").write_text("")
        result = self.run_script()
        self.assertIn("Detected stack: python", result.stdout)

    def test_undetectable_stack_fails_and_writes_nothing(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Could not detect a stack", result.stderr)
        self.assertFalse((self.project / ".claude").exists())

    def test_unknown_argument_fails_and_writes_nothing(self):
        result = self.run_script("ruby")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown argument", result.stderr)
        self.assertFalse((self.project / ".claude").exists())

    # -- existing settings -----------------------------------------------------

    def test_existing_settings_are_merged_not_replaced(self):
        self.write_settings({
            "permissions": {"allow": ["Bash(ls:*)"]},
            "enabledPlugins": {"my-own@market": True},
        })
        result = self.run_script("python")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Merged python plugins into existing", result.stdout)
        merged = self.settings()
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls:*)"]})
        self.assertTrue(merged["enabledPlugins"]["my-own@market"])
        for plugin, enabled in self.template("python")["enabledPlugins"].items():
            self.assertEqual(merged["enabledPlugins"][plugin], enabled)

    def test_merge_is_idempotent(self):
        self.run_script("python")
        first = (self.project / ".claude" / "settings.json").read_bytes()
        result = self.run_script("python")
        self.assertIn("Merged", result.stdout)
        self.assertEqual((self.project / ".claude" / "settings.json").read_bytes(), first)

    # Pins today's behavior: the template wins a conflict, so an explicit
    # `false` the user set for a template plugin is silently flipped to `true`,
    # and no backup is kept. Reported in the PR for audit-F; not changed here.
    def test_template_wins_a_conflicting_plugin_value_with_no_backup(self):
        plugin = next(iter(self.template("python")["enabledPlugins"]))
        self.write_settings({"enabledPlugins": {plugin: False}})
        result = self.run_script("python")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIs(self.settings()["enabledPlugins"][plugin], True)
        self.assertEqual(
            sorted(p.name for p in (self.project / ".claude").iterdir()), ["settings.json"]
        )

    def test_existing_settings_that_are_not_json_are_left_untouched(self):
        path = self.project / ".claude" / "settings.json"
        path.parent.mkdir()
        path.write_text("{ not json")
        result = self.run_script("python")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_text(), "{ not json")

    # -- --local ---------------------------------------------------------------

    def test_local_flag_writes_settings_local_and_leaves_settings_alone(self):
        shared = self.write_settings({"permissions": {"allow": ["Bash(ls:*)"]}})
        before = shared.read_bytes()
        result = self.run_script("python", "--local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(shared.read_bytes(), before)
        self.assertEqual(self.settings("settings.local.json"), self.template("python"))
        self.assertIn("gitignored", result.stdout)


if __name__ == "__main__":
    unittest.main()
