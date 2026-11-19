"""Tests for reviewer_leaderboard.py footer parsing. Run from this directory."""

import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reviewer_leaderboard as lb  # noqa: E402

HEADER = "### Code review\n\nFound 1 blocking issue(s) and 0 non-blocking note(s).\n\n"


class ReviewModel(unittest.TestCase):
    def test_full_footer_buckets_by_model_effort_and_scorer(self):
        body = HEADER + "🤖 Generated with Claude Code, model `claude-sonnet-5-5`, effort `high`, scorer `claude-haiku-5-5` at `xhigh`."
        self.assertEqual("claude-sonnet-5-5@high +scorer claude-haiku-5-5@xhigh", lb.review_model(body))

    def test_old_footer_keeps_the_bare_model(self):
        body = HEADER + "🤖 Generated with Claude Code, model `claude-sonnet-5-5`."
        self.assertEqual("claude-sonnet-5-5", lb.review_model(body))

    def test_effort_without_scorer(self):
        body = HEADER + "🤖 Generated with Claude Code, model `claude-opus-5-5`, effort `medium`."
        self.assertEqual("claude-opus-5-5@medium", lb.review_model(body))

    def test_scorer_model_is_not_read_as_the_reviewer(self):
        body = HEADER + "🤖 Generated with SomeCLI, scorer `claude-haiku-5-5` at `xhigh`."
        self.assertEqual("unknown:somecli", lb.review_model(body))

    def test_provider_paths_still_normalize(self):
        body = HEADER + "🤖 Generated with OpenCode, model `opencode/deepseek-v4-flash-free`."
        self.assertEqual("deepseek-v4-flash", lb.review_model(body))

    def test_not_a_code_review(self):
        self.assertIsNone(lb.review_model("LGTM"))


if __name__ == "__main__":
    unittest.main()
