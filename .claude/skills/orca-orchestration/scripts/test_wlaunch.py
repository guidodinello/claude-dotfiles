"""Tests for wlaunch.py. Run: python3 -m unittest discover -p 'test_*.py' (from this directory)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("WSEND_SETTLE_SECS", "0")
os.environ.setdefault("WLAUNCH_PLAN_WAIT_SECS", "0.2")
os.environ.setdefault("WLAUNCH_PLAN_POLL_SECS", "0.02")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_orca  # noqa: E402
import wlaunch  # noqa: E402

TYPED = "$ claude --model opusplan --permission-mode plan"
PLAN = "plan mode on (shift+tab to cycle)"
PROMPT = "Read .task-brief.md and plan."


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = wlaunch.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def sends(fake):
    return [c for c in fake.calls() if c[:2] == ["terminal", "send"]]


class Create(unittest.TestCase):
    def test_creates_the_worktree_with_the_final_branch_and_no_parent(self):
        with fake_orca.FakeOrca() as fake:
            code, out, _ = run(
                "create", "--repo", "id:r1", "--name", "t1", "--base", "origin/main",
                "--branch", "feat/t1", "--comment", "t1 planning",
            )
            self.assertEqual(0, code)
            self.assertEqual({"worktree": "/wt/x", "branch": "feat/t1"}, json.loads(out))
            self.assertEqual(
                [[
                    "worktree", "create", "--repo", "id:r1", "--name", "t1", "--no-parent",
                    "--base-branch", "origin/main", "--branch", "feat/t1", "--comment", "t1 planning",
                ]],
                fake.calls(),
            )


    def test_no_comment_flag_when_the_comment_is_empty(self):
        with fake_orca.FakeOrca() as fake:
            run("create", "--repo", "id:r1", "--name", "t1", "--base", "origin/main", "--branch", "feat/t1")
            self.assertNotIn("--comment", fake.calls()[0])


class Start(unittest.TestCase):
    def setUp(self):
        self.wt = tempfile.TemporaryDirectory()
        self.addCleanup(self.wt.cleanup)
        self.path = os.path.realpath(self.wt.name)

    def brief(self):
        with open(os.path.join(self.path, ".task-brief.md"), "w", encoding="utf-8") as fh:
            fh.write("brief")

    def start(self):
        return run("start", self.path, "--title", "t1-claude", "--prompt", PROMPT)

    def test_missing_brief_aborts_before_any_terminal_exists(self):
        with fake_orca.FakeOrca() as fake:
            code, _, err = self.start()
            self.assertEqual(1, code)
            self.assertIn("make-brief.py", err)
            self.assertEqual([], fake.calls())

    def test_happy_path_waits_for_plan_mode_then_types_the_prompt_and_presses_enter(self):
        self.brief()
        with fake_orca.FakeOrca(previews=(PLAN, PLAN)) as fake:
            code, out, _ = self.start()
            self.assertEqual(0, code)
            self.assertEqual({"worktree": self.path, "handle": "term_x"}, json.loads(out))
            calls = fake.calls()
            self.assertEqual(
                [
                    ["terminal", "create", "--worktree", f"path:{self.path}", "--title", "t1-claude",
                     "--command", wlaunch.DEFAULT_COMMAND],
                    ["terminal", "wait", "--terminal", "term_x", "--for", "tui-idle", "--timeout-ms", "120000"],
                    ["terminal", "show", "--terminal", "term_x"],
                ],
                calls[:3],
            )
            self.assertEqual(
                [
                    ["terminal", "send", "--terminal", "term_x", "--text", PROMPT],
                    ["terminal", "send", "--terminal", "term_x", "--text", "", "--enter"],
                ],
                sends(fake),
            )

    def test_command_left_typed_at_the_prompt_gets_one_enter_then_the_prompt(self):
        self.brief()
        with fake_orca.FakeOrca(previews=(TYPED, PLAN)) as fake:
            code, _, _ = self.start()
            self.assertEqual(0, code)
            texts = [c[c.index("--text") + 1] for c in sends(fake)]
            self.assertEqual(["", PROMPT, ""], texts)
            self.assertIn("--enter", sends(fake)[0])
            self.assertNotIn("--enter", sends(fake)[1])

    def test_still_typed_after_the_enter_fails_without_sending_the_prompt(self):
        self.brief()
        with fake_orca.FakeOrca(previews=(TYPED, TYPED)) as fake:
            code, _, err = self.start()
            self.assertEqual(1, code)
            self.assertIn("after pressing Enter", err)
            self.assertEqual(1, len(sends(fake)))

    def test_command_only_in_scrollback_is_not_at_the_prompt(self):
        # the command already ran and something else (a dialog) is on screen: no blind Enter
        self.brief()
        scrollback = f"{TYPED}\nDo you trust the files in this folder? (y/n)"
        with fake_orca.FakeOrca(previews=(scrollback, scrollback)) as fake:
            code, _, err = self.start()
            self.assertEqual(1, code)
            self.assertIn("not at the prompt", err)
            self.assertEqual([], sends(fake))

    def test_command_at_prompt_looks_only_at_the_last_non_empty_line(self):
        cmd = wlaunch.DEFAULT_COMMAND
        self.assertTrue(wlaunch.command_at_prompt(f"banner\n❯ {cmd}\n\n", cmd))
        self.assertFalse(wlaunch.command_at_prompt(f"❯ {cmd}\nplan mode on", cmd))
        self.assertFalse(wlaunch.command_at_prompt("", cmd))

    def test_no_plan_mode_and_no_command_at_the_prompt_fails_without_sending_anything(self):
        self.brief()
        with fake_orca.FakeOrca(previews=("$ ", "$ ")) as fake:
            code, _, err = self.start()
            self.assertEqual(1, code)
            self.assertIn("not at the prompt", err)
            self.assertEqual([], sends(fake))

    def test_every_terminal_call_names_the_handle_with_the_flag(self):
        self.brief()
        with fake_orca.FakeOrca(previews=(TYPED, PLAN)) as fake:
            self.start()
            for call in fake.calls():
                if call[:2] in (["terminal", "wait"], ["terminal", "show"], ["terminal", "send"]):
                    self.assertEqual("term_x", call[call.index("--terminal") + 1])
                    self.assertEqual(1, sum(a.startswith("term_") for a in call))

    def test_multiline_prompt_is_refused_before_anything_runs(self):
        self.brief()
        with fake_orca.FakeOrca() as fake:
            code, _, err = run("start", self.path, "--title", "t", "--prompt", "a\nb")
            self.assertEqual(1, code)
            self.assertIn(".orchestrator-answers.md", err)
            self.assertEqual([], fake.calls())

    def test_default_prompt_fits_the_send_limit(self):
        wlaunch._orca.refuse_unsendable(wlaunch.DEFAULT_PROMPT)


if __name__ == "__main__":
    unittest.main()
