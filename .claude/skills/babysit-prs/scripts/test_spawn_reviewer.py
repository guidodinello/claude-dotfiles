"""Unit tests for spawn_reviewer.py. Run: python3 -m unittest test_spawn_reviewer (from this directory)."""

import os
import sys
import unittest
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spawn_reviewer as sr  # ty: ignore[unresolved-import]


def ws(*labels: str) -> list[dict[str, Any]]:
    return [{"label": label, "workspace_id": f"w{i}"} for i, label in enumerate(labels)]


def review(rid: int, body: str) -> dict[str, Any]:
    return {"id": rid, "body": body}


class CapacityTests(unittest.TestCase):
    def test_only_rev_workspaces_count(self) -> None:
        self.assertEqual(sr.count_reviewer_workspaces(ws("fitted", "rev1", "rev22", "review", "rev")), 2)

    def test_refuses_the_fourth_reviewer(self) -> None:
        with self.assertRaises(sr.SpawnError) as ctx:
            sr.check_capacity(ws("rev1", "rev2", "rev3"), 4, 3)
        self.assertEqual(ctx.exception.code, sr.EXIT_REFUSED)

    def test_allows_the_third_reviewer(self) -> None:
        sr.check_capacity(ws("rev1", "rev2", "other"), 3, 3)

    def test_refuses_a_duplicate_for_the_same_pr(self) -> None:
        with self.assertRaises(sr.SpawnError) as ctx:
            sr.check_capacity(ws("rev7"), 7, 3)
        self.assertEqual(ctx.exception.code, sr.EXIT_REFUSED)


class BriefTests(unittest.TestCase):
    def test_substitutes_pr_repo_and_context(self) -> None:
        text = sr.render_brief(1178, "o/r", "Docs only.")
        self.assertIn("Run /code-review on PR 1178 (o/r).", text)
        self.assertIn("do not poll them with sleep. Docs only. Post the review", text)

    def test_no_context_leaves_no_double_space(self) -> None:
        text = sr.render_brief(5, "o/r", "")
        self.assertIn("sleep. Post the review", text)
        self.assertNotIn("  ", text)


class FindNewReviewTests(unittest.TestCase):
    def test_ignores_baseline_and_foreign_reviews(self) -> None:
        reviews = [
            review(1, "### Code review\n\nold"),
            review(2, "looks good to me"),
            review(3, "### Code review\n\nnew"),
        ]
        found = sr.find_new_review(reviews, {1})
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], 3)  # ty: ignore[not-subscriptable]

    def test_none_when_nothing_new(self) -> None:
        self.assertIsNone(sr.find_new_review([review(1, "### Code review")], {1}))

    def test_takes_the_newest_of_several(self) -> None:
        reviews = [review(4, "### Code review a"), review(9, "### Code review b")]
        self.assertEqual(sr.find_new_review(reviews, set())["id"], 9)  # ty: ignore[not-subscriptable]

    def test_null_body_is_skipped(self) -> None:
        self.assertIsNone(sr.find_new_review([{"id": 1, "body": None}], set()))


class VerdictTests(unittest.TestCase):
    def test_clean_needs_marker_and_no_inline_comments(self) -> None:
        body = "### Code review\n\nNo issues found. Checked for bugs."
        self.assertTrue(sr.is_clean(review(1, body), 0))
        self.assertFalse(sr.is_clean(review(1, body), 1))

    def test_findings_are_not_clean(self) -> None:
        self.assertFalse(sr.is_clean(review(1, "### Code review\n\nFound 1 blocking issue(s)."), 0))

    def test_label_args_clean(self) -> None:
        args = sr.label_edit_args(True, {"pending-review"})
        self.assertEqual(
            args,
            ["--remove-label", "pending-review", "--add-label", "reviewed", "--add-label", "ready-to-merge"],
        )

    def test_label_args_with_findings_remove_ready_to_merge(self) -> None:
        args = sr.label_edit_args(False, {"pending-review", "ready-to-merge"})
        removed = [args[i + 1] for i, a in enumerate(args) if a == "--remove-label"]
        added = [args[i + 1] for i, a in enumerate(args) if a == "--add-label"]
        self.assertEqual(sorted(removed), ["pending-review", "ready-to-merge"])
        self.assertEqual(added, ["reviewed"])

    def test_label_args_never_remove_a_label_the_pr_lacks(self) -> None:
        # claude-dotfiles has no pending-review label; gh pr edit --remove-label fails on it
        for clean in (True, False):
            args = sr.label_edit_args(clean, set())
            self.assertNotIn("--remove-label", args)
            self.assertIn("reviewed", args)

    def test_label_args_remove_only_the_present_one(self) -> None:
        args = sr.label_edit_args(False, {"ready-to-merge"})
        self.assertEqual(args, ["--remove-label", "ready-to-merge", "--add-label", "reviewed"])


class DecideCleanTests(unittest.TestCase):
    CLEAN = review(1, "### Code review\n\nNo issues found.")

    def test_clean_when_head_unchanged(self) -> None:
        self.assertTrue(sr.decide_clean(self.CLEAN, 0, "abc", "abc"))

    def test_head_moved_fails_closed(self) -> None:
        self.assertFalse(sr.decide_clean(self.CLEAN, 0, "abc", "def"))

    def test_unknown_reviewed_sha_fails_closed(self) -> None:
        self.assertFalse(sr.decide_clean(self.CLEAN, 0, "", ""))

    def test_findings_stay_unclean_even_if_head_matches(self) -> None:
        self.assertFalse(sr.decide_clean(self.CLEAN, 2, "abc", "abc"))


class RetryTests(unittest.TestCase):
    def test_retries_then_succeeds(self) -> None:
        calls: list[int] = []

        def flaky() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise sr.SpawnError("transient")
            return "ok"

        self.assertEqual(sr.with_retry(flaky, attempts=3, delay=0, sleep=lambda _: None), "ok")

    def test_gives_up_after_the_last_attempt(self) -> None:
        def always() -> None:
            raise sr.SpawnError("down")

        with self.assertRaises(sr.SpawnError):
            sr.with_retry(always, attempts=2, delay=0, sleep=lambda _: None)

    def test_does_not_retry_a_refusal(self) -> None:
        calls: list[int] = []

        def refuse() -> None:
            calls.append(1)
            raise sr.SpawnError("no", sr.EXIT_REFUSED)

        with self.assertRaises(sr.SpawnError):
            sr.with_retry(refuse, attempts=3, delay=0, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)


class PaneBusyRetryTests(unittest.TestCase):
    BUSY = 'herdr agent start failed (1): {"error":{"code":"agent_pane_busy","message":"not an available shell"}}'

    def test_only_agent_pane_busy_is_retryable(self) -> None:
        self.assertTrue(sr.is_pane_busy(sr.SpawnError(self.BUSY)))
        self.assertFalse(sr.is_pane_busy(sr.SpawnError("herdr agent start failed (1): unknown_agent")))

    def test_retries_busy_then_succeeds(self) -> None:
        calls: list[int] = []
        sleeps: list[float] = []

        def start() -> str:
            calls.append(1)
            if len(calls) < 3:
                raise sr.SpawnError(self.BUSY)
            return "started"

        self.assertEqual(sr.retry_pane_busy(start, attempts=5, delay=2.0, sleep=sleeps.append), "started")
        self.assertEqual(sleeps, [2.0, 2.0])

    def test_gives_up_when_it_stays_busy(self) -> None:
        calls: list[int] = []

        def start() -> None:
            calls.append(1)
            raise sr.SpawnError(self.BUSY)

        with self.assertRaises(sr.SpawnError):
            sr.retry_pane_busy(start, attempts=4, delay=0, sleep=lambda _: None)
        self.assertEqual(len(calls), 4)

    def test_other_errors_fail_at_once(self) -> None:
        calls: list[int] = []

        def start() -> None:
            calls.append(1)
            raise sr.SpawnError("herdr agent start failed (1): unknown_agent")

        with self.assertRaises(sr.SpawnError):
            sr.retry_pane_busy(start, attempts=4, delay=0, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)


class CodeReviewContractTests(unittest.TestCase):
    def test_marker_strings_match_the_code_review_skill(self) -> None:
        skill = Path(__file__).resolve().parents[2] / "code-review" / "SKILL.md"
        if not skill.exists():
            self.skipTest("code-review skill not next to babysit-prs")
        text = skill.read_text(encoding="utf-8")
        self.assertIn(sr.REVIEW_HEADER, text)
        self.assertIn(sr.CLEAN_MARKER, text)


if __name__ == "__main__":
    unittest.main()
