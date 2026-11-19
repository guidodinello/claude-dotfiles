import contextlib
import datetime as dt
import io
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import model_retro

PRICES = {"claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_hit": 0.1}, "claude-haiku-5-5": {"input": 0.1, "output": 0.5, "cache_hit": 0.01}}


def turn_line(msg_id, model, effort, output, cache_read=0, write_1h=0):
    usage = {"input_tokens": 0, "output_tokens": output, "cache_read_input_tokens": cache_read, "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": write_1h}}
    return json.dumps({"type": "assistant", "effort": effort, "timestamp": "2026-11-10T12:00:00Z", "message": {"id": msg_id, "model": model, "usage": usage}})


def user_line(text):
    return json.dumps({"type": "user", "timestamp": "2026-11-10T11:59:00Z", "message": {"role": "user", "content": text}})


class RetroTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        project = self.root / "proj"
        project.mkdir()
        review = project / "r1.jsonl"
        review.write_text("\n".join([
            user_line("<command-name>/code-review</command-name> 12"),
            turn_line("m1", "claude-sonnet-5-5", "medium", 1_000_000),
            turn_line("m1", "claude-sonnet-5-5", "medium", 1_000_000),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": "Found 2 blocking issue(s) and 1 non-blocking note(s)."}}),
        ]) + "\n")
        sub = project / "r1" / "subagents"
        sub.mkdir(parents=True)
        (sub / "agent-a.jsonl").write_text(turn_line("h1", "claude-haiku-5-5", "medium", 0, cache_read=1_000_000, write_1h=1_000_000) + "\n")
        (project / "other.jsonl").write_text(user_line("fix the bug, then run /code-review") + "\n" + turn_line("x1", "claude-sonnet-5-5", "medium", 5_000_000) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_counts_subagents_dedupes_messages_and_matches_first_prompt_only(self):
        result = model_retro.collect("code-review", dt.date(2026, 11, 1), dt.date(2026, 11, 30), [self.root], PRICES)
        self.assertEqual(result["sessions"], 1)
        # Sonnet: 1M output once (not twice) = $10. Haiku: 1M cache read $0.01 + 1M 1h write at 2x $0.10 = $0.21.
        self.assertAlmostEqual(result["cost_per_session"]["median"], 10.21, places=2)
        self.assertEqual(result["findings_per_review_median"], 3)
        self.assertEqual(set(result["cost_share"]), {"claude-sonnet-5-5@medium", "claude-haiku-5-5@medium"})

    def test_window_excludes_sessions(self):
        result = model_retro.collect("code-review", dt.date(2026, 11, 11), dt.date(2026, 11, 30), [self.root], PRICES)
        self.assertEqual(result["sessions"], 0)

    def test_verify_items_stay_listed_until_marked_done(self):
        decisions = self.root / "decisions.json"
        decisions.write_text(json.dumps([{"id": "d1", "verify": [{"what": "first review shows sonnet@high", "done": None}]}]))
        with mock.patch.object(model_retro, "DECISIONS_FILE", decisions):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                model_retro.print_open_verifications(model_retro.load_decisions()[0])
            self.assertIn("0. first review shows sonnet@high", out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                model_retro.main(["verified", "--id", "d1", "--item", "0"])
            self.assertTrue(model_retro.load_decisions()[0]["verify"][0]["done"])

    def test_clean_review_counts_as_zero_but_skill_text_does_not(self):
        skill_text = json.dumps({"type": "user", "message": {"role": "user", "content": "post: No issues found. Checked for bugs and CLAUDE.md compliance."}})
        posted = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "input": {"body": "No issues found. Checked for bugs and CLAUDE.md compliance."}}]}})
        clean, unposted = self.root / "clean.jsonl", self.root / "unposted.jsonl"
        clean.write_text(skill_text + "\n" + posted + "\n")
        unposted.write_text(skill_text + "\n")
        self.assertEqual(model_retro.review_findings(model_retro.assistant_text([clean])), 0)
        self.assertIsNone(model_retro.review_findings(model_retro.assistant_text([unposted])))

    def test_short_model_alias_is_priced_as_the_watched_release(self):
        snapshot = {"releases": ["claude-haiku-5-5"], "models": [{"release": "claude-haiku-5-5", "price_1m_input": 0.1, "price_1m_output": 0.5, "price_1m_cache_hit": 0.01}]}
        prices = model_retro.price_table(snapshot)
        self.assertEqual(prices["haiku"], prices["claude-haiku-5-5"])
        self.assertNotIn("sonnet", prices)

    def test_turns_without_any_id_are_all_counted(self):
        path = self.root / "keyless.jsonl"
        line = json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5-5", "usage": {"output_tokens": 1}}})
        path.write_text(line + "\n" + line + "\n")
        self.assertEqual(len(model_retro.turns([path])), 2)

    def test_session_kind_prompts_match_the_files_that_send_them(self):
        skills = Path(__file__).resolve().parents[2]
        owners = {"Run /code-review on PR": skills / "babysit-prs/scripts/spawn_reviewer.py", "Read .task-brief.md": skills / "orca-orchestration/scripts/wlaunch.py", "Your plan is approved and saved in .task-plan.md": skills / "orca-orchestration/scripts/wlaunch.py"}
        kinds = model_retro.aa_frontier.load_roles()["session_kinds"]
        prefixes = {p for rule in kinds.values() for p in rule.get("first_prompt_prefix", [])}
        self.assertEqual(prefixes - set(owners), set(), "add the owning file of each new prefix to this test")
        for prefix, owner in owners.items():
            self.assertIn(prefix, owner.read_text(), f"{owner.name} no longer sends {prefix!r}")

    def test_project_unit_adds_the_sessions_of_one_worktree(self):
        kinds = {"worker": {"first_prompt_prefix": ["Read .task-brief.md", "Your plan is approved"], "unit": "project"}}
        wt = self.root / "wt"
        wt.mkdir()
        (wt / "plan.jsonl").write_text(user_line("Read .task-brief.md") + "\n" + turn_line("p1", "claude-sonnet-5-5", "medium", 1_000_000) + "\n")
        (wt / "code.jsonl").write_text(user_line("Your plan is approved and saved") + "\n" + turn_line("c1", "claude-sonnet-5-5", "high", 1_000_000) + "\n")
        with mock.patch.object(model_retro.aa_frontier, "load_roles", return_value={"session_kinds": kinds}):
            result = model_retro.collect("worker", dt.date(2026, 11, 1), dt.date(2026, 11, 30), [self.root], PRICES, require="claude-sonnet-5-5@high")
        self.assertEqual(result["sessions"], 1)
        self.assertAlmostEqual(result["cost_per_session"]["median"], 20.0, places=2)

    def test_unknown_model_is_reported_not_priced(self):
        self.assertIsNone(model_retro.turn_cost({"model": "gpt-x", "usage": {"output_tokens": 5}}, PRICES))


if __name__ == "__main__":
    unittest.main()
