"""Tests for how sync.sh merges settings.base.json into a config dir's
settings.json: removals propagate, edits replace, local keys survive, every
dropped key is named. Run: python3 -m unittest discover -s tests"""

import json
import os
import subprocess
import unittest
from pathlib import Path

from test_sync import ScriptCase

MANIFEST = ".sync-settings-manifest.json"
GUARD = "hooks/guard-bash.sh"


class MergeCase(ScriptCase):
    def base(self) -> dict:
        return json.loads((self.src / "settings.base.json").read_text())

    def write_base(self, data: dict) -> None:
        self.write(self.src / "settings.base.json", json.dumps(data, indent=2))

    def edit_base(self, fn) -> None:
        data = self.base()
        fn(data)
        self.write_base(data)

    def guard_hooks(self, settings: dict) -> list[dict]:
        return [
            h
            for e in settings["hooks"]["PreToolUse"]
            for h in e["hooks"]
            if h.get("command", "").endswith(GUARD)
        ]

    def manifest_path(self, cfg: Path | None = None) -> Path:
        return (cfg or self.cfg) / MANIFEST


class RemovalsPropagateTest(MergeCase):
    def test_a_rule_removed_from_the_base_leaves_the_live_file_on_the_next_sync(self):
        self.sync()
        rule = self.base()["permissions"]["allow"][0]
        self.edit_base(lambda b: b["permissions"]["allow"].remove(rule))
        self.sync()
        self.assertNotIn(rule, self.settings()["permissions"]["allow"])

    def test_a_foreign_rule_survives_the_removal(self):
        self.sync()
        live = self.settings()
        live["permissions"]["allow"].append("Bash(installer:*)")
        live["permissions"]["deny"].append("Read(secret)")
        self.write_settings(live)
        rule = self.base()["permissions"]["allow"][0]
        self.edit_base(lambda b: b["permissions"]["allow"].remove(rule))
        self.sync()
        permissions = self.settings()["permissions"]
        self.assertNotIn(rule, permissions["allow"])
        self.assertIn("Bash(installer:*)", permissions["allow"])
        self.assertIn("Read(secret)", permissions["deny"])

    def test_a_removed_deny_rule_is_dropped_and_named_in_a_warning(self):
        self.sync()
        rule = self.base()["permissions"]["deny"][-1]
        self.edit_base(lambda b: b["permissions"]["deny"].remove(rule))
        result = self.sync()
        self.assertNotIn(rule, self.settings()["permissions"]["deny"])
        warn = [ln for ln in result.stdout.splitlines() if "WARN" in ln and "Removed deny rule" in ln]
        self.assertEqual(len(warn), 1, result.stdout)
        self.assertIn(rule, warn[0])

    def test_a_removed_allow_rule_is_named_at_info_level(self):
        self.sync()
        rule = self.base()["permissions"]["allow"][0]
        self.edit_base(lambda b: b["permissions"]["allow"].remove(rule))
        result = self.sync()
        line = [ln for ln in result.stdout.splitlines() if rule in ln]
        self.assertEqual(len(line), 1, result.stdout)
        self.assertIn("INFO", line[0])
        self.assertNotIn("WARN", line[0])

    def test_a_removed_ask_rule_is_a_warning_because_it_loosens_policy(self):
        self.edit_base(lambda b: b["permissions"].update(ask=["Bash(x:*)", "Bash(y:*)"]))
        self.sync()
        self.edit_base(lambda b: b["permissions"]["ask"].remove("Bash(x:*)"))
        result = self.sync()
        self.assertNotIn("Bash(x:*)", self.settings()["permissions"]["ask"])
        warn = [ln for ln in result.stdout.splitlines() if "Bash(x:*)" in ln]
        self.assertEqual(len(warn), 1, result.stdout)
        self.assertIn("WARN", warn[0])

    def test_without_a_manifest_a_removed_rule_stays_but_retired_rules_still_go(self):
        self.sync()
        self.manifest_path().unlink()
        rule = self.base()["permissions"]["allow"][0]
        self.edit_base(lambda b: b["permissions"]["allow"].remove(rule))
        live = self.settings()
        live["permissions"]["deny"].append("Read(.env)")  # in RETIRED_PERMISSION_RULES
        self.write_settings(live)
        self.sync()
        permissions = self.settings()["permissions"]
        self.assertIn(rule, permissions["allow"])
        self.assertNotIn("Read(.env)", permissions["deny"])

    def test_an_invalid_manifest_warns_and_falls_back(self):
        self.sync()
        self.write(self.manifest_path(), "{ not json")
        rule = self.base()["permissions"]["allow"][0]
        self.edit_base(lambda b: b["permissions"]["allow"].remove(rule))
        result = self.sync()
        self.assertIn("WARN", result.stdout)
        self.assertIn(MANIFEST, result.stdout)
        self.assertIn(rule, self.settings()["permissions"]["allow"])
        json.loads(self.manifest_path().read_text())  # rewritten as valid JSON


class BrokenBaseTest(MergeCase):
    """A base that lost a list the last sync recorded must not read as "every
    entry was removed": fail closed, write nothing, keep the manifest."""

    def break_base(self, name: str) -> None:
        def empty(b):
            b.clear()

        def no_deny(b):
            del b["permissions"]["deny"]

        def empty_deny(b):
            b["permissions"]["deny"] = []

        def renamed_deny(b):
            b["permissions"]["denied"] = b["permissions"].pop("deny")

        def no_hooks(b):
            del b["hooks"]

        self.edit_base({"empty": empty, "no_deny": no_deny, "empty_deny": empty_deny,
                        "renamed_deny": renamed_deny, "no_hooks": no_hooks}[name])

    def assert_refused(self, name: str, names: str) -> None:
        self.sync()
        live_before = (self.cfg / "settings.json").read_text()
        manifest_before = self.manifest_path().read_text()
        self.break_base(name)
        result = self.sync(check=False)
        self.assertNotEqual(result.returncode, 0, name)
        self.assertIn(names, result.stderr, name)
        self.assertIn("Refusing to merge", result.stderr, name)
        self.assertEqual((self.cfg / "settings.json").read_text(), live_before, name)
        self.assertEqual(self.manifest_path().read_text(), manifest_before, name)
        self.assertEqual(self.backups(), [], name)
        self.assertNotIn("Removed", result.stdout, name)

    def test_a_base_with_nothing_in_it_is_refused(self):
        self.assert_refused("empty", "permissions.allow, permissions.deny, hooks")

    def test_a_base_without_the_deny_list_is_refused(self):
        self.assert_refused("no_deny", "permissions.deny")

    def test_a_base_with_an_empty_deny_list_is_refused(self):
        self.assert_refused("empty_deny", "permissions.deny")

    def test_a_base_with_the_deny_list_renamed_is_refused(self):
        self.assert_refused("renamed_deny", "permissions.deny")

    def test_a_base_without_hooks_is_refused(self):
        self.assert_refused("no_hooks", "hooks")

    def test_the_guards_and_deny_rules_survive_a_refused_sync(self):
        self.sync()
        deny_before = self.settings()["permissions"]["deny"]
        self.assertGreater(len(deny_before), 0)
        self.break_base("empty")
        self.sync(check=False)
        settings = self.settings()
        self.assertEqual(settings["permissions"]["deny"], deny_before)
        self.assertEqual(len(self.guard_hooks(settings)), 1)

    def test_deleting_the_manifest_is_the_way_through_for_a_deliberate_removal(self):
        self.sync()
        deny_before = self.settings()["permissions"]["deny"]
        self.break_base("no_deny")
        self.manifest_path().unlink()
        result = self.sync(check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.settings()["permissions"]["deny"], deny_before)

    def test_removing_some_rules_but_not_all_is_still_a_normal_removal(self):
        self.sync()
        rule = self.base()["permissions"]["deny"][-1]
        self.edit_base(lambda b: b["permissions"]["deny"].remove(rule))
        result = self.sync()
        self.assertNotIn(rule, self.settings()["permissions"]["deny"])
        self.assertNotIn("Refusing", result.stderr)


class HooksTest(MergeCase):
    def test_an_edited_hook_replaces_the_old_copy(self):
        self.sync()

        def add_timeout(b):
            for e in b["hooks"]["PreToolUse"]:
                for h in e["hooks"]:
                    if h["command"].endswith(GUARD):
                        h["timeout"] = 7

        self.edit_base(add_timeout)
        self.sync()
        guards = self.guard_hooks(self.settings())
        self.assertEqual(len(guards), 1, guards)
        self.assertEqual(guards[0]["timeout"], 7)

    def test_an_edited_hook_is_not_duplicated_even_without_a_manifest(self):
        self.sync()
        self.manifest_path().unlink()
        self.edit_base(
            lambda b: b["hooks"]["PreToolUse"][0]["hooks"][0].update(timeout=7)
        )
        self.sync()
        self.assertEqual(len(self.guard_hooks(self.settings())), 1)

    def test_a_hook_removed_from_the_base_disappears(self):
        self.sync()
        self.edit_base(lambda b: b["hooks"].pop("Stop"))
        result = self.sync()
        self.assertNotIn("Stop", self.settings()["hooks"])
        removed = [ln for ln in result.stdout.splitlines() if "dev-docs-index-check.py" in ln]
        self.assertEqual(len(removed), 1, result.stdout)
        self.assertIn("WARN", removed[0])  # a removed hook may be a guard

    def test_a_foreign_hook_in_the_same_event_survives_a_removal(self):
        self.sync()
        live = self.settings()
        foreign = {"matcher": "*", "hooks": [{"type": "command", "command": "installer-hook"}]}
        live["hooks"]["Stop"].append(foreign)
        self.write_settings(live)
        self.edit_base(lambda b: b["hooks"].pop("Stop"))
        self.sync()
        self.assertEqual(self.settings()["hooks"]["Stop"], [foreign])

    def test_a_foreign_hook_sharing_an_entry_with_a_base_hook_survives(self):
        self.sync()
        live = self.settings()
        foreign = {"type": "command", "command": "installer-hook"}
        live["hooks"]["PreToolUse"][0]["hooks"].append(foreign)
        self.write_settings(live)
        self.edit_base(
            lambda b: b["hooks"]["PreToolUse"][0]["hooks"][0].update(timeout=7)
        )
        self.sync()
        commands = [h["command"] for e in self.settings()["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertIn("installer-hook", commands)
        self.assertEqual(len(self.guard_hooks(self.settings())), 1)


class LocalKeysTest(MergeCase):
    def test_model_and_effort_level_survive_a_sync(self):
        self.write_settings({"model": "sonnet", "effortLevel": "high"})
        self.sync()
        settings = self.settings()
        self.assertEqual(settings["model"], "sonnet")
        self.assertEqual(settings["effortLevel"], "high")

    def test_dropped_and_overridden_keys_are_named_but_never_their_values(self):
        secret = "tok-planted-secret-value"
        self.write_settings(
            {
                "env": {"API_TOKEN": secret},
                "theme": "dark",
                "permissions": {"defaultMode": "plan"},
                "skipWorkflowUsageWarning": False,
            }
        )
        result = self.sync()
        out = result.stdout
        self.assertIn("Dropped live key: env", out)
        self.assertIn("Dropped live key: theme", out)
        self.assertIn("Overrode live key: permissions.defaultMode", out)
        self.assertIn("Overrode live key: skipWorkflowUsageWarning", out)
        self.assertNotIn(secret, out + result.stderr)
        self.assertNotIn("env", self.settings())
        self.assertEqual(
            self.settings()["permissions"]["defaultMode"], self.base()["permissions"]["defaultMode"]
        )

    def test_a_clean_sync_reports_no_dropped_keys(self):
        self.sync()
        result = self.sync()
        self.assertNotIn("Dropped live key", result.stdout)
        self.assertNotIn("Overrode live key", result.stdout)


class FailureIsolationTest(MergeCase):
    def test_one_invalid_settings_file_does_not_stop_the_other_dirs_or_opencode(self):
        work = self.home / ".claude-work"
        self.write(self.cfg / "settings.json", "{ not json")
        work.mkdir()
        self.write(work / ".dotfiles-config-dir", str(work))  # marked: a sync target
        self.write(self.repo / ".config" / "opencode" / "opencode.json", "{}")
        result = self.sync(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.cfg / "settings.json").read_text(), "{ not json")
        self.assertTrue((work / "settings.json").is_file())
        self.assertTrue((self.home / ".config" / "opencode" / "opencode.json").is_symlink())
        self.assertIn(str(self.cfg), result.stderr)
        self.assertFalse(self.manifest_path().exists())


class PathTest(MergeCase):
    def test_a_home_with_ampersand_and_pipe_resolves_the_config_dir_literally(self):
        self.home = self.home.parent / "a&b|c"
        self.home.mkdir()
        self.cfg = self.home / ".claude"
        self.sync()
        settings = self.settings()
        self.assertEqual(settings["statusLine"]["command"], f"{self.cfg}/statusline.sh")
        self.assertNotIn("{{CONFIG_DIR}}", json.dumps(settings))
        commands = [h["command"] for e in settings["hooks"]["PreToolUse"] for h in e["hooks"]]
        self.assertIn(f"{self.cfg}/{GUARD}", commands)


class LiveOnlyTest(MergeCase):
    def seed_foreign(self):
        self.sync()
        live = self.settings()
        live["permissions"]["allow"].append("Bash(installer:*)")
        live["permissions"]["deny"].append("Read(secret)")
        live["hooks"].setdefault("Notification", []).append(
            {"hooks": [{"type": "command", "command": "installer-hook"}]}
        )
        self.write_settings(live)

    def test_every_run_prints_the_live_only_counts(self):
        self.seed_foreign()
        result = self.sync()
        line = [ln for ln in result.stdout.splitlines() if "Live-only" in ln]
        self.assertEqual(len(line), 1, result.stdout)
        self.assertIn("allow 1", line[0])
        self.assertIn("deny 1", line[0])
        self.assertIn("hooks 1", line[0])
        self.assertNotIn("installer-hook", result.stdout)

    def test_the_env_var_lists_each_entry(self):
        self.seed_foreign()
        result = subprocess.run(
            ["bash", str(self.repo / "sync.sh")],
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(self.home), "SYNC_LIST_LIVE_ONLY": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Bash(installer:*)", result.stdout)
        self.assertIn("Read(secret)", result.stdout)
        self.assertIn("installer-hook", result.stdout)


class IdempotencyTest(MergeCase):
    def test_a_second_sync_writes_no_backup_and_leaves_the_manifest_alone(self):
        self.sync()
        manifest, settings = self.manifest_path().read_text(), self.settings()
        result = self.sync()
        self.assertIn("already up to date", result.stdout)
        self.assertEqual(self.manifest_path().read_text(), manifest)
        self.assertEqual(self.settings(), settings)
        self.assertEqual(self.backups(), [])

    def test_an_up_to_date_dir_with_no_manifest_gets_one_seeded_without_a_backup(self):
        self.sync()
        self.manifest_path().unlink()
        result = self.sync()
        self.assertIn("already up to date", result.stdout)
        self.assertTrue(self.manifest_path().is_file())
        self.assertEqual(self.backups(), [])

    def test_the_manifest_is_never_linked_into_the_repo_or_pruned_as_a_backup(self):
        self.sync()
        self.assertTrue(self.manifest_path().is_file())
        self.assertFalse(self.manifest_path().is_symlink())
        self.assertFalse((self.src / MANIFEST).exists())
        self.sync()
        self.assertTrue(self.manifest_path().is_file())


if __name__ == "__main__":
    unittest.main()
