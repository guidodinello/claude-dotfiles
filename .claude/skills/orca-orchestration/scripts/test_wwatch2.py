"""Tests for wwatch2.py and _transcript.own_pr_urls.
Run: python3 -m unittest discover -p 'test_*.py' (from this directory)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wwatch2  # noqa: E402

LIMITS = wwatch2.Limits(idle=100, bash=500, grace=50)
PLAN = {"id": "plan1", "name": "ExitPlanMode"}
URL = "https://github.com/o/r/pull/7"


def snap(**kw):
    base = {"age": 0, "stamp": 1.0, "via_sub": False, "pending": None, "text": "", "prs": []}
    base.update(kw)
    return base


def detect(s, mem, elapsed=0, alive=True):
    return [line for line, _ in wwatch2.detect("w", "proj", s, mem, elapsed, alive, LIMITS)]


class Ready(unittest.TestCase):
    def test_a_new_plan_is_reported_once(self):
        mem = wwatch2.Memory()
        self.assertEqual(["READY w ExitPlanMode"], detect(snap(pending=PLAN), mem))
        self.assertEqual([], detect(snap(pending=PLAN), mem, elapsed=10))

    def test_a_different_plan_id_is_reported_again(self):
        mem = wwatch2.Memory()
        detect(snap(pending=PLAN), mem)
        again = detect(snap(pending={"id": "plan2", "name": "ExitPlanMode"}), mem, elapsed=10)
        self.assertEqual(["READY w ExitPlanMode"], again)

    def test_a_plan_pending_at_start_waits_for_the_grace_period(self):
        mem = wwatch2.Memory(base_wait="plan1")
        self.assertEqual([], detect(snap(pending=PLAN), mem, elapsed=10))
        self.assertEqual(["READY w ExitPlanMode"], detect(snap(pending=PLAN), mem, elapsed=60))

    def test_a_reported_plan_never_turns_into_stuck(self):
        mem = wwatch2.Memory()
        detect(snap(pending=PLAN), mem)
        self.assertEqual([], detect(snap(pending=PLAN, age=9999), mem, elapsed=9999))


class OwnPr(unittest.TestCase):
    def test_a_url_in_plain_text_is_not_a_pr_event(self):
        # the 10 Nov misfire: a reviewer's text mentions the PR URL
        s = snap(text=f"reviewing {URL}", prs=[])
        self.assertEqual([], detect(s, wwatch2.Memory()))

    def test_urls_from_the_workers_own_gh_pr_create_are_reported_once_each(self):
        mem = wwatch2.Memory()
        self.assertEqual([f"PR w ['{URL}']"], detect(snap(prs=[URL]), mem))
        self.assertEqual([], detect(snap(prs=[URL]), mem))
        other = "https://github.com/o/r/pull/8"
        self.assertEqual([f"PR w ['{other}']"], detect(snap(prs=[URL, other]), mem))

    def test_a_url_present_at_start_is_baseline_not_an_event(self):
        mem = wwatch2.Memory(prs_seen={URL})
        self.assertEqual([], detect(snap(prs=[URL]), mem))


class Idle(unittest.TestCase):
    def test_idle_is_reported_once_until_the_transcript_moves(self):
        mem = wwatch2.Memory()
        self.assertEqual([], detect(snap(age=50), mem, elapsed=200))
        self.assertEqual(["IDLE w age 150"], detect(snap(age=150), mem, elapsed=200))
        self.assertEqual([], detect(snap(age=300), mem, elapsed=300))
        self.assertEqual(["IDLE w age 150"], detect(snap(age=150, stamp=2.0), mem, elapsed=500))

    def test_a_pending_bash_gets_the_long_limit(self):
        bash = {"id": "b1", "name": "Bash"}
        mem = wwatch2.Memory()
        self.assertEqual([], detect(snap(age=200, pending=bash), mem, elapsed=300))
        self.assertEqual(["STUCK:Bash w age 600"], detect(snap(age=600, pending=bash), mem, elapsed=700))

    def test_nothing_before_the_idle_window_has_passed(self):
        self.assertEqual([], detect(snap(age=500), wwatch2.Memory(), elapsed=10))


class Dead(unittest.TestCase):
    def test_needs_two_polls_in_a_row(self):
        mem = wwatch2.Memory()
        self.assertEqual([], detect(snap(), mem, alive=False))
        self.assertEqual([], detect(snap(), mem, alive=True))
        self.assertEqual([], detect(snap(), mem, alive=False))
        self.assertEqual(["DEAD w no live claude process in its worktree"], detect(snap(), mem, alive=False))

    def test_reported_once(self):
        mem = wwatch2.Memory()
        for _ in range(2):
            detect(snap(), mem, alive=False)
        self.assertEqual([], detect(snap(), mem, alive=False))

    def test_unknown_liveness_never_counts(self):
        mem = wwatch2.Memory()
        for _ in range(5):
            self.assertEqual([], detect(snap(), mem, alive=None))

    def test_not_counted_while_claude_may_still_be_starting(self):
        mem = wwatch2.Memory()
        for _ in range(5):
            self.assertEqual([], detect(None, mem, elapsed=10, alive=False))
        self.assertEqual("NOTRANSCRIPT w proj", detect(None, mem, elapsed=200, alive=False)[-1])


class ClaudePids(unittest.TestCase):
    def test_matches_only_the_claude_binary(self):
        ps = "\n".join([
            "  101 claude --plugin-dir /x/Application Support/y --model opusplan",
            "  102 /Users/me/.local/bin/claude --output-format stream-json",
            "  103 claude",
            "  104 claude --resume abc",
            "  105 python3 -I /Users/me/.claude/skills/orca-orchestration/scripts/wwatch2.py 1 /w",
            "  106 vim claude.md",
            "  107 node /opt/claude/index.js",
            "  108 /Users/me/orca/workspaces/claude-dotfiles/x/run.sh",
            "  109 claudette --x",
            "  garbage",
        ])
        self.assertEqual(["101", "102", "103", "104"], wwatch2.claude_pids(ps))


class Run(unittest.TestCase):
    def setUp(self):
        self.t = 0.0
        self.lines = []

    def clock(self):
        return self.t

    def sleep(self, secs):
        self.t += secs

    def go(self, snaps, follow, probe=lambda: None, minutes=10):
        script = iter(snaps)
        last = [None]

        def snap_fn(_project):
            last[0] = next(script, last[0])
            return last[0]

        code = wwatch2.run(
            ["w"], minutes, follow, projects={"w": "proj"}, probe=probe, limits=LIMITS, poll=10,
            clock=self.clock, sleep=self.sleep, out=self.lines.append, snap_fn=snap_fn,
        )
        return code

    def test_one_shot_prints_the_first_event_and_returns(self):
        self.go([snap(), snap(pending=PLAN), snap(pending=PLAN), snap(prs=[URL])], follow=False)
        self.assertEqual(["READY w ExitPlanMode"], self.lines)

    def test_one_shot_times_out(self):
        self.go([snap()], follow=False, minutes=1)
        self.assertEqual(["TIMEOUT"], self.lines)

    def test_follow_keeps_going_and_does_not_repeat_a_pending_plan(self):
        working = snap(stamp=5.0)
        self.go(
            [snap(), snap(pending=PLAN), snap(pending=PLAN), snap(pending=PLAN), working, snap(prs=[URL], stamp=6.0)],
            follow=True, minutes=1,
        )
        self.assertEqual(["READY w ExitPlanMode", f"PR w ['{URL}']", "TIMEOUT"], self.lines)

    def test_follow_ends_when_every_worker_is_dead(self):
        cwd = os.path.realpath(tempfile.gettempdir())
        script = iter([snap()])
        wwatch2.run(
            [cwd], 10, True, projects={cwd: "proj"}, probe=lambda: set(), limits=LIMITS, poll=10,
            clock=self.clock, sleep=self.sleep, out=self.lines.append, snap_fn=lambda _p: next(script, snap()),
        )
        self.assertEqual(1, len(self.lines))
        self.assertTrue(self.lines[0].startswith("DEAD"))


def write_rows(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in rows)


def tool_use(tool_id, command, name="Bash"):
    return {"message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": tool_id, "name": name, "input": {"command": command}}]}}


def tool_result(tool_id, content):
    return {"message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": content}]}}


class OwnPrUrls(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.transcript = os.path.join(self.dir.name, "s1.jsonl")

    def urls(self, rows, sub_rows=None):
        write_rows(self.transcript, rows)
        if sub_rows is not None:
            write_rows(os.path.join(self.dir.name, "s1", "subagents", "a.jsonl"), sub_rows)
        return wwatch2.tx.own_pr_urls(self.transcript)

    def test_reads_the_result_of_gh_pr_create(self):
        rows = [tool_use("t1", "gh pr create --title x"), tool_result("t1", f"{URL}\n")]
        self.assertEqual([URL], self.urls(rows))

    def test_handles_a_token_prefix_a_compound_command_and_list_content(self):
        cmd = "cd x && GH_TOKEN=$(gh auth token -u me) gh pr create --fill"
        rows = [tool_use("t1", cmd), tool_result("t1", [{"type": "text", "text": f"created {URL}"}])]
        self.assertEqual([URL], self.urls(rows))

    def test_ignores_urls_from_other_commands_text_and_pr_link_rows(self):
        rows = [
            tool_use("t1", "gh pr view 7"), tool_result("t1", URL),
            {"message": {"role": "assistant", "content": [{"type": "text", "text": f"see {URL}"}]}},
            {"type": "pr-link", "prUrl": URL},
            tool_use("t2", "echo hi", name="Read"), tool_result("t2", URL),
        ]
        self.assertEqual([], self.urls(rows))

    def test_ignores_a_pending_gh_pr_create_with_no_result_yet(self):
        self.assertEqual([], self.urls([tool_use("t1", "gh pr create")]))

    def test_finds_a_pr_opened_by_a_subagent(self):
        sub = [tool_use("s1", "gh pr create"), tool_result("s1", URL)]
        self.assertEqual([URL], self.urls([], sub))

    def test_no_duplicates_in_order(self):
        other = "https://github.com/o/r/pull/9"
        rows = [
            tool_use("a", "gh pr create"), tool_result("a", URL),
            tool_use("b", "gh pr create"), tool_result("b", f"{other} {URL}"),
        ]
        self.assertEqual([URL, other], self.urls(rows))


class Cli(unittest.TestCase):
    """The script end to end, on a temporary Claude config dir with synthetic transcripts."""

    def run_cli(self, *args, config, **env):
        full = {**os.environ, "CLAUDE_CONFIG_DIR": config, "WWATCH_POLL_SECS": "0.05",
                "WWATCH_IDLE_SECS": "-1", **env}
        return subprocess.run(
            [sys.executable, "-I", os.path.join(HERE, "wwatch2.py"), *args],
            capture_output=True, text=True, env=full, timeout=60,
        )

    def test_one_shot_reports_ready_for_a_pending_plan(self):
        with tempfile.TemporaryDirectory() as config, tempfile.TemporaryDirectory() as wt:
            wt = os.path.realpath(wt)
            base = os.path.join(config, "projects", wwatch2.tx.sanitize(wt))
            plan = {"message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "p1", "name": "ExitPlanMode", "input": {"plan": "x"}}]}}
            write_rows(os.path.join(base, "s.jsonl"), [plan])
            proc = self.run_cli("1", wt, config=config, WWATCH_GRACE_SECS="-1")
            self.assertEqual(f"READY {wt} ExitPlanMode", proc.stdout.strip(), proc.stderr)

    def test_no_transcript_is_reported_and_the_pidfile_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as config, tempfile.TemporaryDirectory() as wt:
            pidfile = os.path.join(config, "w.pid")
            proc = self.run_cli("--pidfile", pidfile, "1", wt, config=config)
            self.assertTrue(proc.stdout.startswith("NOTRANSCRIPT"), proc.stderr)
            self.assertFalse(os.path.exists(pidfile))

    def test_missing_arguments_print_usage(self):
        with tempfile.TemporaryDirectory() as config:
            proc = self.run_cli(config=config)
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("usage", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
