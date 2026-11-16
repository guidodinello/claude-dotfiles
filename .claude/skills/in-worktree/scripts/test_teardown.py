"""Unit tests for teardown.py. Run: python3 -I test_teardown.py."""

import os
import sys
import unittest
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teardown as td  # ty: ignore[unresolved-import]

MAIN = "/r/main"
WT = "/r/main-wt-x"
PORCELAIN = f"""worktree {MAIN}
HEAD aaa
branch refs/heads/development

worktree {WT}
HEAD bbb
branch refs/heads/fix/x

worktree /r/main-wt-rev1
HEAD ccc
detached
"""


def worktrees() -> list[dict[str, Any]]:
    return td.parse_worktree_list(PORCELAIN)


def make(**over: Any) -> list[tuple[str, ...]]:
    kw: dict[str, Any] = {
        "target": WT,
        "worktrees": worktrees(),
        "cwd": MAIN,
        "dirty": [],
        "dep_symlinks": [],
        "label": None,
        "workspaces": [],
        "self_workspace_id": "wSelf",
        "force": False,
        "merged_prs": [],
    }
    kw.update(over)
    return td.plan(**kw)


def refused(**over: Any) -> str:
    with unittest.TestCase().assertRaises(td.TeardownError) as ctx:
        make(**over)
    assert ctx.exception.code == td.EXIT_REFUSED
    return str(ctx.exception)


class ParseTests(unittest.TestCase):
    def test_worktree_list(self) -> None:
        wts = worktrees()
        self.assertEqual([w["path"] for w in wts], [MAIN, WT, "/r/main-wt-rev1"])
        self.assertEqual(wts[1]["branch"], "fix/x")
        self.assertIsNone(wts[2]["branch"])

    def test_status(self) -> None:
        self.assertEqual(
            td.parse_status(" M a.py\n?? dir/\n?? link\n"), [(" M", "a.py"), ("??", "dir"), ("??", "link")]
        )


class RefusalTests(unittest.TestCase):
    def test_main_checkout(self) -> None:
        self.assertIn("main checkout", refused(target=MAIN, cwd="/elsewhere"))

    def test_unknown_path(self) -> None:
        self.assertIn("not a worktree", refused(target="/r/other"))

    def test_cwd_inside(self) -> None:
        self.assertIn("cwd", refused(cwd=WT + "/backend"))

    def test_dirty(self) -> None:
        self.assertIn("uncommitted", refused(dirty=["a.py"]))

    def test_dirty_with_force(self) -> None:
        self.assertEqual(make(dirty=["a.py"], force=True)[0][0], "remove_worktree")

    def test_symlink_only_is_not_dirty(self) -> None:
        actions = make(dep_symlinks=[WT + "/backend/.venv"])
        self.assertEqual(actions[0], ("unlink", WT + "/backend/.venv"))

    def test_label_no_match(self) -> None:
        self.assertIn("no herdr workspace", refused(label="x", workspaces=[]))

    def test_label_no_match_with_force_continues(self) -> None:
        self.assertEqual(make(label="x", workspaces=[], force=True)[0][0], "remove_worktree")

    def test_label_many(self) -> None:
        ws = [{"label": "x", "workspace_id": "w1"}, {"label": "x", "workspace_id": "w2"}]
        self.assertIn("matches 2", refused(label="x", workspaces=ws))

    def test_self_workspace(self) -> None:
        self.assertIn("running this script", refused(label="x", workspaces=[{"label": "x", "workspace_id": "wSelf"}]))


class ActionTests(unittest.TestCase):
    def test_order(self) -> None:
        actions = make(
            label="x",
            workspaces=[{"label": "x", "workspace_id": "w1"}],
            dep_symlinks=[WT + "/l"],
            merged_prs=[{"number": 7, "headRefOid": "bbb"}],
        )
        self.assertEqual(
            [a[0] for a in actions],
            ["close_workspace", "unlink", "remove_worktree", "prune", "delete_branch"],
        )
        self.assertEqual(actions[0], ("close_workspace", "w1"))

    def test_resolves_id_not_label(self) -> None:
        actions = make(
            label="x", workspaces=[{"label": "x", "workspace_id": "w9"}, {"label": "y", "workspace_id": "w2"}]
        )
        self.assertEqual(actions[0], ("close_workspace", "w9"))


class BranchDecisionTests(unittest.TestCase):
    def test_merged_and_tip_equal(self) -> None:
        self.assertTrue(td.branch_decision("b", "t", [{"number": 1, "headRefOid": "t"}])[0])

    def test_merged_but_tip_moved(self) -> None:
        self.assertFalse(td.branch_decision("b", "t2", [{"number": 1, "headRefOid": "t"}])[0])

    def test_not_merged(self) -> None:
        self.assertFalse(td.branch_decision("b", "t", [])[0])

    def test_detached(self) -> None:
        self.assertFalse(td.branch_decision(None, "t", [{"number": 1, "headRefOid": "t"}])[0])

    def test_plan_keeps_unmerged_branch(self) -> None:
        self.assertEqual(make()[-1][0], "keep_branch")


if __name__ == "__main__":
    unittest.main()
