"""Unit tests for spawn_reviewer.py. Run: python3 -m unittest test_spawn_reviewer (from this directory)."""

import os
import sys
import unittest
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
        args = sr.label_edit_args(True)
        self.assertIn("ready-to-merge", args)
        self.assertEqual(args[args.index("--add-label") + 1], "reviewed")
        self.assertNotIn("--remove-label ready-to-merge", " ".join(args))

    def test_label_args_with_findings_remove_ready_to_merge(self) -> None:
        args = sr.label_edit_args(False)
        removed = [args[i + 1] for i, a in enumerate(args) if a == "--remove-label"]
        added = [args[i + 1] for i, a in enumerate(args) if a == "--add-label"]
        self.assertEqual(sorted(removed), ["pending-review", "ready-to-merge"])
        self.assertEqual(added, ["reviewed"])


if __name__ == "__main__":
    unittest.main()
