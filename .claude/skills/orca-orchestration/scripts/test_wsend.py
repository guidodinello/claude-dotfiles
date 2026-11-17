"""Tests for wsend.py. Run: python3 -m unittest discover -p 'test_*.py' (from this directory)."""

import contextlib
import io
import os
import sys
import unittest

os.environ.setdefault("WSEND_SETTLE_SECS", "0")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_orca  # noqa: E402
import wsend  # noqa: E402


def send(*argv):
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = wsend.main(list(argv))
    return code, err.getvalue()


class WSend(unittest.TestCase):
    def test_text_is_typed_without_enter_then_a_bare_enter_follows(self):
        with fake_orca.FakeOrca() as fake:
            code, _ = send("term_x", "hello there")
            self.assertEqual(0, code)
            self.assertEqual(
                [
                    ["terminal", "send", "--terminal", "term_x", "--text", "hello there"],
                    ["terminal", "send", "--terminal", "term_x", "--text", "", "--enter"],
                ],
                fake.calls(),
            )

    def test_menu_choice_is_the_bare_number_with_no_enter(self):
        with fake_orca.FakeOrca() as fake:
            self.assertEqual(0, send("term_x", "--menu", "3")[0])
            self.assertEqual([["terminal", "send", "--terminal", "term_x", "--text", "3"]], fake.calls())

    def test_handle_is_never_positional(self):
        with fake_orca.FakeOrca() as fake:
            send("term_x", "hi")
            for call in fake.calls():
                self.assertEqual("term_x", call[call.index("--terminal") + 1])
                self.assertEqual(1, sum(a.startswith("term_") for a in call))

    def test_multiline_and_long_text_are_refused_without_calling_orca(self):
        with fake_orca.FakeOrca() as fake:
            for text in ("two\nlines", "x" * 401):
                code, err = send("term_x", text)
                self.assertEqual(2, code)
                self.assertIn(".orchestrator-answers.md", err)
            self.assertEqual([], fake.calls())

    def test_orca_failure_exits_non_zero_and_stops(self):
        with fake_orca.FakeOrca(fail="terminal send") as fake:
            code, err = send("term_x", "hi")
            self.assertEqual(1, code)
            self.assertIn("boom", err)
            self.assertEqual(1, len(fake.calls()))

    def test_needs_text_or_menu_but_not_both(self):
        for argv in (["term_x"], ["term_x", "hi", "--menu", "1"]):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                wsend.main(argv)


if __name__ == "__main__":
    unittest.main()
