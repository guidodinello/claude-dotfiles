"""Unit tests for watch.py. Run: python3 -m unittest test_watch (from this directory)."""

import contextlib
import io
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch  # noqa: E402


def check(name, status="COMPLETED", conclusion="SUCCESS"):
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


def raw_pr(**kw):
    base = {
        "state": "OPEN",
        "mergeStateStatus": "CLEAN",
        "labels": [],
        "reviews": [],
        "comments": [],
        "statusCheckRollup": [check("a")],
        "headRefOid": "abcdef123456",
    }
    base.update(kw)
    return base


class ClassifyChecks(unittest.TestCase):
    def test_no_checks_is_pending(self):
        self.assertEqual(watch.classify_checks([]), ("pending", []))
        self.assertEqual(watch.classify_checks(None), ("pending", []))

    def test_queued_in_progress_and_cancelled_are_pending(self):
        for c in (
            check("a", "QUEUED", ""),
            check("a", "IN_PROGRESS", ""),
            check("a", "COMPLETED", "CANCELLED"),
        ):
            self.assertEqual(watch.classify_checks([c]), ("pending", []), c)

    def test_failure_wins_over_pending(self):
        rollup = [check("a", "IN_PROGRESS", ""), check("b", conclusion="FAILURE")]
        self.assertEqual(watch.classify_checks(rollup), ("failing", ["b"]))

    def test_status_context(self):
        err = {"__typename": "StatusContext", "context": "ci/x", "state": "ERROR"}
        wait = {"__typename": "StatusContext", "context": "ci/x", "state": "PENDING"}
        self.assertEqual(watch.classify_checks([err]), ("failing", ["ci/x"]))
        self.assertEqual(watch.classify_checks([wait]), ("pending", []))

    def test_all_green_and_skipped(self):
        rollup = [check("a"), check("b", conclusion="SKIPPED")]
        self.assertEqual(watch.classify_checks(rollup), ("passing", []))


class DiffPr(unittest.TestCase):
    def snap(self, prev=None, **kw):
        return watch.normalize_pr(raw_pr(**kw), prev)

    def test_unknown_merge_keeps_last_known(self):
        prev = self.snap(mergeStateStatus="CLEAN")
        cur = self.snap(prev, mergeStateStatus="UNKNOWN")
        self.assertEqual(cur["merge"], "CLEAN")

    def test_baseline_has_no_events_but_records_failures(self):
        seen = set()
        cur = self.snap(statusCheckRollup=[check("a", conclusion="FAILURE")])
        self.assertEqual(watch.diff_pr(None, cur, seen), [])
        self.assertEqual(seen, {"a@abcdef1"})

    def test_baseline_terminal_state_is_an_event(self):
        events = watch.diff_pr(None, self.snap(state="MERGED"), set())
        self.assertEqual(watch.match_until(events, {"merged"}), "merged")

    def test_failure_reported_once_per_head(self):
        seen = set()
        prev = self.snap()
        bad = self.snap(prev, statusCheckRollup=[check("a", conclusion="FAILURE")])
        first = watch.diff_pr(prev, bad, seen)
        self.assertIn("check-failed a", [t for _, t in first])
        self.assertNotIn("check-failed a", [t for _, t in watch.diff_pr(bad, bad, seen)])
        pushed = self.snap(bad, statusCheckRollup=[check("a", conclusion="FAILURE")], headRefOid="9999999aaaa")
        self.assertIn("check-failed a", [t for _, t in watch.diff_pr(bad, pushed, seen)])

    def test_review_comment_label_push_dirty(self):
        prev = self.snap()
        cur = self.snap(
            prev,
            reviews=[{"id": 1, "author": {"login": "bot"}, "state": "COMMENTED"}],
            comments=[{"id": 2, "author": {"login": "me"}}],
            labels=[{"name": "reviewed"}],
            headRefOid="1111111abc",
            mergeStateStatus="DIRTY",
        )
        events = watch.diff_pr(prev, cur, set())
        texts = [t for _, t in events]
        self.assertIn("review bot COMMENTED", texts)
        self.assertIn("comment me", texts)
        self.assertIn("label +reviewed", texts)
        self.assertIn("push 1111111", texts)
        self.assertIn("dirty (merge conflict)", texts)
        self.assertEqual(watch.match_until(events, {"label:reviewed"}), "label:reviewed")
        self.assertIsNone(watch.match_until(events, {"label:other", "merged"}))

    def test_checks_aggregate_change_is_info_only(self):
        prev = self.snap(statusCheckRollup=[])
        cur = self.snap(prev)
        events = watch.diff_pr(prev, cur, set())
        self.assertEqual([t for _, t in events], ["checks passing"])
        self.assertIsNone(watch.match_until(events, watch.BASE_UNTIL))


class DiffAgents(unittest.TestCase):
    def rec(self, status="working", sc=1, cs=0):
        return watch.agent_snapshot({"agent_status": status, "state_change_seq": sc, "completion_seq": cs})

    def test_status_change(self):
        self.assertEqual(watch.diff_agents(self.rec(), self.rec("idle", 2)), ["working->idle"])

    def test_blip_between_polls_is_seen_through_the_seq(self):
        self.assertEqual(watch.diff_agents(self.rec(sc=1), self.rec(sc=3, cs=1)), ["completed working"])
        self.assertEqual(watch.diff_agents(self.rec(sc=1), self.rec(sc=3)), ["state changed, still working"])

    def test_gone_and_baseline(self):
        self.assertEqual(watch.diff_agents(self.rec(), watch.agent_snapshot(None)), ["gone"])
        self.assertEqual(watch.diff_agents(None, self.rec()), [])

    def test_find_by_name_or_pane(self):
        agents = [{"name": "w", "pane_id": "p:1"}, {"pane_id": "p:2"}]
        self.assertIs(watch.find_agent(agents, "w"), agents[0])
        self.assertIs(watch.find_agent(agents, "p:2"), agents[1])
        self.assertIsNone(watch.find_agent(agents, "zzz"))


class Loop(unittest.TestCase):
    def run_loop(self, watcher, **kw):
        out = io.StringIO()
        ticks = {"n": 0}

        def clock():
            return ticks["n"]

        def sleep(sec):
            ticks["n"] += sec

        with contextlib.redirect_stdout(out):
            code = watch.run(watcher, 100, 10, kw.get("first", False), sleep=sleep, clock=clock)
        return code, out.getvalue()

    def test_keeps_watching_after_agent_event_and_pr_pending(self):
        pr_states = iter([raw_pr(statusCheckRollup=[])] * 3 + [raw_pr(state="MERGED")])
        agent_polls = iter(
            [
                [{"name": "a1", "agent_status": "working", "state_change_seq": 1}],
                [{"name": "a1", "agent_status": "idle", "state_change_seq": 2}],
                [{"name": "a1", "agent_status": "idle", "state_change_seq": 2}],
                [{"name": "a1", "agent_status": "idle", "state_change_seq": 2}],
            ]
        )
        w = watch.Watcher(
            [7],
            ["a1"],
            {"merged"},
            fetch_pr=lambda n: next(pr_states),
            fetch_agent_list=lambda: next(agent_polls),
        )
        code, out = self.run_loop(w)
        self.assertEqual(code, 0)
        self.assertIn("PR 7 status state=OPEN merge=CLEAN checks=pending", out)
        self.assertNotIn("check-failed", out)
        self.assertIn("AGENT a1 working->idle", out)
        self.assertIn("DONE PR 7 merged", out)

    def test_timeout_names_remaining_targets(self):
        w = watch.Watcher([7], [], {"merged"}, fetch_pr=lambda n: raw_pr())
        code, out = self.run_loop(w)
        self.assertEqual(code, 124)
        self.assertIn("TIMEOUT PR 7", out)

    def test_poll_error_is_not_an_event(self):
        def boom(_):
            raise watch.WatchError("net down")

        w = watch.Watcher([7], [], {"merged"}, fetch_pr=boom)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(w.poll(), 0)

    def test_state_file_carries_events_across_restarts(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            first = watch.Watcher([7], [], {"merged"}, state_path=path, fetch_pr=lambda n: raw_pr())
            with contextlib.redirect_stdout(io.StringIO()):
                first.poll()
            fail = raw_pr(statusCheckRollup=[check("a", conclusion="FAILURE")])
            second = watch.Watcher([7], [], {"merged"}, state_path=path, fetch_pr=lambda n: fail)
            code, out = self.run_loop(second, first=True)
            self.assertEqual(code, 0)
            self.assertIn("PR 7 check-failed a", out)
            third = watch.Watcher([7], [], {"merged"}, state_path=path, fetch_pr=lambda n: fail)
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                third.poll()
            self.assertNotIn("check-failed", buf.getvalue())

    def test_unknown_until_rejected(self):
        with self.assertRaises(SystemExit):
            watch.parse_until("merged,nonsense")


if __name__ == "__main__":
    unittest.main()
