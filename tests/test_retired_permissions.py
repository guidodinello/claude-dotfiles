"""Tests for the rules retired from settings.base.json by the permissions audit
and for the fail-closed settings of the two guard hooks.
Run: python3 -m unittest discover -s tests"""

import unittest

from test_settings_merge import MergeCase

REMOVED_ALLOW_RULES = (
    "Bash(rtk:*)",
    "Bash(op read:*)",
    "Bash(security find-generic-password:*)",
)


class RemovedAllowRulesTest(MergeCase):
    def seed_live_file_with_the_removed_rules(self) -> None:
        live = self.settings() if (self.cfg / "settings.json").exists() else {"permissions": {"allow": []}}
        live["permissions"]["allow"].extend(REMOVED_ALLOW_RULES)
        self.write_settings(live)

    def assert_gone(self) -> None:
        allow = self.settings()["permissions"]["allow"]
        for rule in REMOVED_ALLOW_RULES:
            with self.subTest(rule=rule):
                self.assertNotIn(rule, allow)

    def test_the_base_no_longer_allows_them(self):
        allow = self.base()["permissions"]["allow"]
        for rule in REMOVED_ALLOW_RULES:
            with self.subTest(rule=rule):
                self.assertNotIn(rule, allow)
        self.assertIn("Bash(rtk gain:*)", allow)

    def test_a_dir_with_a_manifest_loses_them_on_the_next_sync(self):
        self.sync()
        self.seed_live_file_with_the_removed_rules()
        self.sync()
        self.assert_gone()

    def test_a_dir_without_a_manifest_loses_them_through_the_retired_list(self):
        self.sync()
        self.manifest_path().unlink()
        self.seed_live_file_with_the_removed_rules()
        self.sync()
        self.assert_gone()

    def test_a_first_sync_into_an_existing_settings_file_drops_them(self):
        self.seed_live_file_with_the_removed_rules()
        self.sync()
        self.assert_gone()
        self.assertIn("Bash(rtk gain:*)", self.settings()["permissions"]["allow"])


class GuardEntriesFailClosedTest(MergeCase):
    def live_guards(self) -> list[dict]:
        return [
            h
            for e in self.settings()["hooks"]["PreToolUse"]
            for h in e["hooks"]
            if h.get("command", "").endswith(("hooks/guard-bash.sh", "hooks/guard-env-files.sh"))
        ]

    def test_both_guards_block_when_they_fail_or_time_out(self):
        self.sync()
        guards = self.live_guards()
        self.assertEqual(len(guards), 2)
        for hook in guards:
            with self.subTest(command=hook["command"]):
                self.assertEqual(hook.get("onFailure"), "block")
                self.assertEqual(hook.get("timeout"), 10)

    def test_an_old_entry_without_the_fields_is_replaced_not_duplicated(self):
        self.sync()
        live = self.settings()
        for entry in live["hooks"]["PreToolUse"]:
            for hook in entry["hooks"]:
                hook.pop("onFailure", None)
                hook.pop("timeout", None)
        self.write_settings(live)
        self.sync()
        guards = self.live_guards()
        self.assertEqual(len(guards), 2, guards)
        for hook in guards:
            self.assertEqual(hook.get("onFailure"), "block")
            self.assertEqual(hook.get("timeout"), 10)
        commands = [h["command"] for h in guards]
        self.assertEqual(len(set(commands)), 2)

    def test_the_engram_marketplace_is_pinned_to_a_full_commit(self):
        ref = self.base()["extraKnownMarketplaces"]["engram"]["source"].get("ref", "")
        self.assertRegex(ref, r"^[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
