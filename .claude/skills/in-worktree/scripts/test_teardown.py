"""Unit tests for teardown.py. Run: python3 -I test_teardown.py."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

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
        "in_herdr": False,
        "head_reachable": True,
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


class FailClosedTests(unittest.TestCase):
    def test_in_herdr_without_workspace_id_refuses(self) -> None:
        ws = [{"label": "x", "workspace_id": "w1"}]
        self.assertIn("HERDR_WORKSPACE_ID", refused(label="x", workspaces=ws, in_herdr=True, self_workspace_id=None))

    def test_outside_herdr_without_workspace_id_is_fine(self) -> None:
        ws = [{"label": "x", "workspace_id": "w1"}]
        actions = make(label="x", workspaces=ws, in_herdr=False, self_workspace_id=None)
        self.assertEqual(actions[0], ("close_workspace", "w1"))

    def test_unreachable_detached_head_refuses(self) -> None:
        self.assertIn("lose commits", refused(target="/r/main-wt-rev1", head_reachable=False))

    def test_unreachable_detached_head_with_force(self) -> None:
        self.assertEqual(make(target="/r/main-wt-rev1", head_reachable=False, force=True)[0][0], "remove_worktree")

    def test_reachable_detached_head_is_fine(self) -> None:
        self.assertEqual(make(target="/r/main-wt-rev1")[0][0], "remove_worktree")


class DepSymlinkTests(unittest.TestCase):
    def test_known_dep_links(self) -> None:
        for rel in ("backend/.venv", "frontend/web/node_modules", "node_modules"):
            self.assertTrue(td.is_dep_symlink(rel), rel)

    def test_other_symlinks_are_not_deps(self) -> None:
        for rel in ("ext_data", "backend/venv", "notes/node_modules_backup"):
            self.assertFalse(td.is_dep_symlink(rel), rel)


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


HOOK = "/r/main/" + td.REPO_HOOK_REL


class RepoHookPlanTests(unittest.TestCase):
    def test_hook_runs_after_workspace_close_and_before_removal(self) -> None:
        actions = make(
            label="x",
            workspaces=[{"label": "x", "workspace_id": "w1"}],
            dep_symlinks=[WT + "/l"],
            repo_hook=HOOK,
        )
        self.assertEqual(
            [a[0] for a in actions],
            ["close_workspace", "repo_teardown_hook", "unlink", "remove_worktree", "prune", "keep_branch"],
        )
        self.assertEqual(actions[1], ("repo_teardown_hook", HOOK, WT))

    def test_no_hook_plans_nothing_extra(self) -> None:
        self.assertNotIn("repo_teardown_hook", [a[0] for a in make()])

    def test_refusals_plan_no_hook(self) -> None:
        self.assertIn("main checkout", refused(target=MAIN, cwd="/elsewhere", repo_hook=HOOK))
        self.assertIn("uncommitted", refused(dirty=["a.py"], repo_hook=HOOK))


class FindRepoHookTests(unittest.TestCase):
    def _make_hook(self, root: str) -> str:
        path = Path(root) / td.REPO_HOOK_REL
        path.parent.mkdir(parents=True)
        path.write_text("#!/bin/sh\n")
        return str(path)

    def test_prefers_the_main_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as main, tempfile.TemporaryDirectory() as wt:
            main_hook = self._make_hook(main)
            self._make_hook(wt)
            self.assertEqual(td.find_repo_hook(main, wt), main_hook)

    def test_falls_back_to_the_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as main, tempfile.TemporaryDirectory() as wt:
            wt_hook = self._make_hook(wt)
            self.assertEqual(td.find_repo_hook(main, wt), wt_hook)

    def test_none_when_neither_has_one(self) -> None:
        with tempfile.TemporaryDirectory() as main, tempfile.TemporaryDirectory() as wt:
            self.assertIsNone(td.find_repo_hook(main, wt))


class RunRepoHookTests(unittest.TestCase):
    def test_runs_bash_with_script_and_worktree(self) -> None:
        done = subprocess.CompletedProcess([], 0, stdout="ok\n", stderr="")
        with mock.patch.object(td.subprocess, "run", autospec=True, return_value=done) as run:
            td.run_repo_hook("/s/teardown-worktree.sh", WT)
        self.assertEqual(run.call_args.args[0], ["bash", "/s/teardown-worktree.sh", WT])

    def test_nonzero_exit_does_not_raise(self) -> None:
        failed = subprocess.CompletedProcess([], 1, stdout="", stderr="boom\n")
        with mock.patch.object(td.subprocess, "run", autospec=True, return_value=failed):
            td.run_repo_hook("/s/t.sh", WT)

    def test_expected_failures_do_not_raise(self) -> None:
        for exc in (
            subprocess.TimeoutExpired("bash", 1),
            OSError("no bash"),
            UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "invalid continuation byte"),
        ):
            with mock.patch.object(td.subprocess, "run", autospec=True, side_effect=exc):
                td.run_repo_hook("/s/t.sh", WT)

    def test_non_utf8_hook_output_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "hook.sh"
            script.write_text("printf 'caf\\xe9\\n'\nexit 0\n")
            td.run_repo_hook(str(script), WT)

    def test_execute_dispatches_the_hook_before_removal(self) -> None:
        calls: list[str] = []
        with (
            mock.patch.object(td, "run_repo_hook", autospec=True, side_effect=lambda *_: calls.append("hook")),
            mock.patch.object(td, "run", autospec=True, side_effect=lambda *_a, **_k: calls.append("run") or ""),
        ):
            td.execute([("repo_teardown_hook", HOOK, WT), ("remove_worktree", WT)], MAIN)
        self.assertEqual(calls, ["hook", "run"])


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
