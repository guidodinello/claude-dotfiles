"""Tests for sync.sh, select.sh, add_file.sh and promote.sh, run against a throwaway copy
of the scripts and a throwaway HOME. Run: python3 -m unittest discover -s tests"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = ["sync.sh", "select.sh", "add_file.sh", "promote.sh"]


class ScriptCase(unittest.TestCase):
    """A fake checkout (the real scripts and settings.base.json, a tiny
    .claude tree) plus a fake HOME, so nothing touches the real ones."""

    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        # realpath: sync.sh resolves its target with `pwd`, and /tmp is a
        # symlink on macOS.
        tmp = tmp.resolve()
        self.repo = tmp / "repo"
        self.home = tmp / "home"
        self.cfg = self.home / ".claude"
        self.home.mkdir()

        (self.repo / "lib").mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(REPO / name, self.repo / name)
        shutil.copy2(REPO / "lib" / "link.sh", self.repo / "lib" / "link.sh")
        self.src = self.repo / ".claude"
        self.write(self.src / "agents" / "a.md", "agent")
        self.write(self.src / "hooks" / "h.sh", "#!/bin/sh\n")
        self.write(self.src / "skills" / "s" / "SKILL.md", "skill")
        shutil.copy2(REPO / ".claude" / "settings.base.json", self.src / "settings.base.json")

    @staticmethod
    def write(path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_script(
        self, name: str, *args: str, check: bool = True, path_prefix: Path | None = None
    ) -> subprocess.CompletedProcess:
        env = {**os.environ, "HOME": str(self.home)}
        if path_prefix is not None:
            env["PATH"] = f"{path_prefix}{os.pathsep}{env['PATH']}"
        result = subprocess.run(
            ["bash", str(self.repo / name), *args], capture_output=True, text=True, env=env
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def sync(self, check: bool = True) -> subprocess.CompletedProcess:
        return self.run_script("sync.sh", check=check)

    def settings(self, cfg: Path | None = None) -> dict:
        return json.loads(((cfg or self.cfg) / "settings.json").read_text())

    def write_settings(self, data: dict) -> None:
        self.write(self.cfg / "settings.json", json.dumps(data))

    def backups(self) -> list[str]:
        return sorted(p.name for p in self.cfg.glob("settings.json.bak*"))


class SyncLinksTest(ScriptCase):
    def test_links_every_file_but_the_settings_sources(self):
        self.sync()
        for rel in ("agents/a.md", "hooks/h.sh", "skills/s/SKILL.md"):
            link = self.cfg / rel
            self.assertTrue(link.is_symlink(), rel)
            self.assertEqual(link.resolve(), (self.src / rel).resolve())
        self.assertFalse((self.cfg / "settings.base.json").exists())
        self.assertFalse((self.cfg / "settings.json").is_symlink())

    def test_does_not_link_backups_or_bytecode(self):
        self.write(self.src / "settings.json.bak", "{}")
        self.write(self.src / "skills" / "s" / "scripts" / "__pycache__" / "x.pyc", "")
        self.sync()
        self.assertFalse((self.cfg / "settings.json.bak").exists())
        self.assertFalse((self.cfg / "skills" / "s" / "scripts").exists())

    def test_existing_file_is_backed_up_then_linked(self):
        self.write(self.cfg / "agents" / "a.md", "mine")
        self.sync()
        self.assertTrue((self.cfg / "agents" / "a.md").is_symlink())
        self.assertEqual((self.cfg / "agents" / "a.md.bak").read_text(), "mine")

    def test_syncs_existing_alternate_profiles_only(self):
        work = self.home / ".claude-work"
        work.mkdir()
        self.sync()
        self.assertTrue((work / "agents" / "a.md").is_symlink())
        self.assertEqual(sorted(p.name for p in self.home.glob(".claude*")), [".claude", ".claude-work"])

    def test_explicit_target_syncs_only_that_dir(self):
        target = self.home / "elsewhere"
        self.run_script("sync.sh", str(target))
        self.assertTrue((target / "agents" / "a.md").is_symlink())
        self.assertFalse(self.cfg.exists())

    def test_prunes_links_to_files_removed_from_the_repo(self):
        self.write(self.src / "guidelines" / "old" / "gone.md", "x")
        self.sync()
        gone = self.cfg / "guidelines" / "old" / "gone.md"
        self.assertTrue(gone.is_symlink())

        shutil.rmtree(self.src / "guidelines")
        foreign = self.cfg / "debug" / "latest"
        foreign.parent.mkdir()
        foreign.symlink_to(self.home / "not-there.txt")
        self.sync()

        self.assertFalse(gone.is_symlink())
        self.assertFalse((self.cfg / "guidelines").exists(), "emptied dirs are removed")
        self.assertTrue(foreign.is_symlink(), "a dangling link that is not ours is kept")
        self.assertTrue((self.cfg / "agents" / "a.md").is_symlink())


class SyncSettingsTest(ScriptCase):
    def test_generates_settings_with_the_config_dir_resolved(self):
        self.sync()
        settings = self.settings()
        self.assertEqual(settings["statusLine"]["command"], f"{self.cfg}/statusline.sh")
        self.assertNotIn("{{CONFIG_DIR}}", json.dumps(settings))
        self.assertEqual(self.backups(), [])

    def test_keeps_local_keys_and_overwrites_the_rest(self):
        self.write_settings(
            {
                "autoMode": {"learned": True},
                "enabledPlugins": {"p@m": True},
                "outputStyle": "Gentleman",
                "model": "something-local",
            }
        )
        self.sync()
        settings = self.settings()
        self.assertEqual(settings["autoMode"], {"learned": True})
        self.assertEqual(settings["enabledPlugins"], {"p@m": True})
        self.assertEqual(settings["outputStyle"], "Gentleman")
        base = json.loads((self.src / "settings.base.json").read_text())
        self.assertEqual(settings["model"], base["model"])

    def test_keeps_installer_hooks_and_permissions(self):
        installer_hook = {"matcher": "*", "hooks": [{"type": "command", "command": "installer-hook"}]}
        self.write_settings(
            {
                "hooks": {"PreToolUse": [installer_hook], "Stop": [installer_hook]},
                "permissions": {"allow": ["Bash(installer:*)"], "deny": ["Read(secret)"]},
            }
        )
        self.sync()
        settings = self.settings()
        self.assertIn(installer_hook, settings["hooks"]["PreToolUse"])
        self.assertEqual(settings["hooks"]["Stop"], [installer_hook])
        self.assertIn("Bash(installer:*)", settings["permissions"]["allow"])
        self.assertIn("Read(secret)", settings["permissions"]["deny"])
        base = json.loads((self.src / "settings.base.json").read_text())
        for rule in base["permissions"]["allow"]:
            self.assertIn(rule, settings["permissions"]["allow"])

    def test_drops_retired_hook_commands(self):
        kept = {"type": "command", "command": "keep-me"}
        self.write_settings(
            {
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]},
                        {"matcher": "Edit", "hooks": [{"type": "command", "command": "rtk hook claude"}, kept]},
                    ]
                }
            }
        )
        self.sync()
        entries = self.settings()["hooks"]["PreToolUse"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertNotIn("rtk hook claude", commands)
        self.assertIn({"matcher": "Edit", "hooks": [kept]}, entries)

    def test_second_run_changes_nothing(self):
        self.write_settings({"model": "old"})
        self.sync()
        first, backups = self.settings(), self.backups()
        self.assertEqual(len(backups), 1)
        result = self.sync()
        self.assertIn("already up to date", result.stdout)
        self.assertEqual(self.settings(), first)
        self.assertEqual(self.backups(), backups)

    def test_refuses_to_overwrite_invalid_json(self):
        self.write(self.cfg / "settings.json", "{ not json")
        result = self.sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.cfg / "settings.json").read_text(), "{ not json")

    def test_keeps_only_the_newest_timestamped_backups(self):
        self.write_settings({"model": "old"})
        stamped = [f"settings.json.bak-2026010{n}-000000" for n in range(1, 6)]
        other = ["settings.json.bak", "settings.json.bak-engram", "settings.json.bak-mcp-20260101"]
        for name in stamped + other:
            self.write(self.cfg / name, "{}")
        self.sync()
        backups = self.backups()
        for name in other:
            self.assertIn(name, backups, "backups sync.sh did not make are kept")
        kept = [b for b in backups if b not in other]
        self.assertEqual(len(kept), 3)
        self.assertEqual(kept[:2], stamped[-2:], "the two newest old ones survive")
        self.assertNotIn(kept[2], stamped, "plus the backup this run made")


class SelectTest(ScriptCase):
    def select(self, *picks: str) -> None:
        """Run select.sh with a stand-in fzf that picks exactly `picks`."""
        bin_dir = self.home / "bin"
        fake_fzf = self.write(
            bin_dir / "fzf",
            "#!/bin/sh\ncat > \"$HOME/offered.txt\"\ncat \"$HOME/picks.txt\"\n",
        )
        fake_fzf.chmod(0o755)
        self.write(self.home / "picks.txt", "".join(f"{p}\n" for p in picks))
        self.run_script("select.sh", path_prefix=bin_dir)

    def offered(self) -> list[str]:
        return (self.home / "offered.txt").read_text().split()

    def test_offers_every_category_but_not_the_settings_sources(self):
        self.write(self.src / "rules" / "r.md", "rule")
        self.write(self.src / "CLAUDE.md", "global")
        self.select("rules/r.md")
        offered = self.offered()
        for item in ("skills/s", "agents/a.md", "hooks/h.sh", "rules/r.md", "CLAUDE.md"):
            self.assertIn(item, offered)
        self.assertNotIn("settings.base.json", offered)

    def test_links_only_what_was_picked(self):
        self.write(self.src / "rules" / "r.md", "rule")
        self.select("rules/r.md", "skills/s")
        self.assertTrue((self.cfg / "rules" / "r.md").is_symlink())
        self.assertTrue((self.cfg / "skills" / "s" / "SKILL.md").is_symlink())
        self.assertFalse((self.cfg / "agents").exists())


class MoveIntoRepoTest(ScriptCase):
    def setUp(self):
        super().setUp()
        self.work = self.home / ".claude-work"
        self.work.mkdir()
        self.sync()

    def assert_linked_everywhere(self, rel: str):
        self.assertTrue((self.src / rel).is_file(), "moved into the repo")
        for cfg in (self.cfg, self.work):
            self.assertEqual((cfg / rel).resolve(), (self.src / rel).resolve(), cfg.name)

    def test_add_file_moves_a_file_and_links_every_profile(self):
        self.write(self.cfg / "agents" / "new.md", "new")
        self.run_script("add_file.sh", str(self.cfg / "agents" / "new.md"))
        self.assert_linked_everywhere("agents/new.md")

    def test_add_file_moves_a_directory(self):
        self.write(self.cfg / "skills" / "new" / "SKILL.md", "new")
        self.write(self.cfg / "skills" / "new" / "scripts" / "x.py", "x")
        self.run_script("add_file.sh", str(self.cfg / "skills" / "new"))
        self.assert_linked_everywhere("skills/new/SKILL.md")
        self.assert_linked_everywhere("skills/new/scripts/x.py")

    def test_promote_moves_a_project_skill_and_links_every_profile(self):
        project_skill = self.home / "project" / ".claude" / "skills" / "p"
        self.write(project_skill / "SKILL.md", "p")
        self.run_script("promote.sh", str(project_skill))
        self.assert_linked_everywhere("skills/p/SKILL.md")
        self.assertFalse(project_skill.exists())

    def test_promote_refuses_to_overwrite_a_repo_file(self):
        clash = self.write(self.home / "project" / ".claude" / "agents" / "a.md", "other")
        result = self.run_script("promote.sh", str(clash), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.src / "agents" / "a.md").read_text(), "agent")
        self.assertTrue(clash.exists())


if __name__ == "__main__":
    unittest.main()
