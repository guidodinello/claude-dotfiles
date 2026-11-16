"""Unit tests for watch.py. Run: python3 -m unittest test_watch (from this directory)."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import watch  # noqa: E402  # ty: ignore[unresolved-import]


def check(name: str, status: str = "COMPLETED", conclusion: str = "SUCCESS") -> dict[str, Any]:
    return {"__typename": "CheckRun", "name": name, "status": status, "conclusion": conclusion}


def raw_pr(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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


def texts(events: list[watch.Event]) -> list[str]:
    return [t for _, t in events]


class ClassifyChecks(unittest.TestCase):
    def test_no_checks_is_pending(self) -> None:
        self.assertEqual(watch.classify_checks([]), ("pending", []))
        self.assertEqual(watch.classify_checks(None), ("pending", []))

    def test_queued_in_progress_and_cancelled_are_pending(self) -> None:
        for c in (
            check("a", "QUEUED", ""),
            check("a", "IN_PROGRESS", ""),
            check("a", "COMPLETED", "CANCELLED"),
        ):
            self.assertEqual(watch.classify_checks([c]), ("pending", []), c)

    def test_failure_wins_over_pending(self) -> None:
        rollup = [check("a", "IN_PROGRESS", ""), check("b", conclusion="FAILURE")]
        self.assertEqual(watch.classify_checks(rollup), ("failing", ["b"]))

    def test_status_context(self) -> None:
        err = {"__typename": "StatusContext", "context": "ci/x", "state": "ERROR"}
        wait = {"__typename": "StatusContext", "context": "ci/x", "state": "PENDING"}
        self.assertEqual(watch.classify_checks([err]), ("failing", ["ci/x"]))
        self.assertEqual(watch.classify_checks([wait]), ("pending", []))

    def test_all_green_and_skipped(self) -> None:
        rollup = [check("a"), check("b", conclusion="SKIPPED")]
        self.assertEqual(watch.classify_checks(rollup), ("passing", []))


class DiffPr(unittest.TestCase):
    def snap(self, prev: watch.Snap | None = None, **kw: Any) -> watch.Snap:
        return watch.normalize_pr(raw_pr(**kw), prev)

    def test_unknown_merge_keeps_last_known(self) -> None:
        prev = self.snap(mergeStateStatus="CLEAN")
        cur = self.snap(prev, mergeStateStatus="UNKNOWN")
        self.assertEqual(cur["merge"], "CLEAN")

    def test_baseline_has_no_events_but_records_failures(self) -> None:
        seen: set[str] = set()
        cur = self.snap(statusCheckRollup=[check("a", conclusion="FAILURE")])
        self.assertEqual(watch.diff_pr(None, cur, seen), [])
        self.assertEqual(seen, {"a@abcdef1"})

    def test_baseline_terminal_state_is_an_event(self) -> None:
        events = watch.diff_pr(None, self.snap(state="MERGED"), set())
        self.assertEqual(watch.terminal_hit(events), "merged")

    def test_failure_reported_once_per_head(self) -> None:
        seen: set[str] = set()
        prev = self.snap()
        bad = self.snap(prev, statusCheckRollup=[check("a", conclusion="FAILURE")])
        self.assertIn("check-failed a", texts(watch.diff_pr(prev, bad, seen)))
        self.assertNotIn("check-failed a", texts(watch.diff_pr(bad, bad, seen)))
        pushed = self.snap(bad, statusCheckRollup=[check("a", conclusion="FAILURE")], headRefOid="9999999aaaa")
        self.assertIn("check-failed a", texts(watch.diff_pr(bad, pushed, seen)))

    def test_review_comment_label_push_dirty(self) -> None:
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
        for expected in (
            "review bot COMMENTED",
            "comment me",
            "label +reviewed",
            "push 1111111",
            "dirty (merge conflict)",
        ):
            self.assertIn(expected, texts(events))
        self.assertEqual(watch.count_wake(events, {"label:reviewed"}), 1)
        self.assertEqual(watch.count_wake(events, {"label:other", "merged"}), 0)
        self.assertIsNone(watch.terminal_hit(events))

    def test_checks_aggregate_change_is_info_only(self) -> None:
        prev = self.snap(statusCheckRollup=[])
        events = watch.diff_pr(prev, self.snap(prev), set())
        self.assertEqual(texts(events), ["checks passing"])
        self.assertEqual(watch.count_wake(events, watch.BASE_UNTIL), 0)


class DiffAgents(unittest.TestCase):
    def rec(self, status: str = "working", sc: int = 1, cs: int = 0) -> watch.Snap:
        return watch.agent_snapshot({"agent_status": status, "state_change_seq": sc, "completion_seq": cs})

    def test_status_change(self) -> None:
        self.assertEqual(watch.diff_agents(self.rec(), self.rec("idle", 2)), ["working->idle"])

    def test_blip_between_polls_is_seen_through_the_seq(self) -> None:
        self.assertEqual(watch.diff_agents(self.rec(sc=1), self.rec(sc=3, cs=1)), ["completed working"])
        self.assertEqual(watch.diff_agents(self.rec(sc=1), self.rec(sc=3)), ["state changed, still working"])

    def test_gone_and_baseline(self) -> None:
        self.assertEqual(watch.diff_agents(self.rec(), watch.agent_snapshot(None)), ["gone"])
        self.assertEqual(watch.diff_agents(None, self.rec()), [])

    def test_find_by_name_or_pane(self) -> None:
        agents = [{"name": "w", "pane_id": "p:1"}, {"pane_id": "p:2"}]
        self.assertIs(watch.find_agent(agents, "w"), agents[0])
        self.assertIs(watch.find_agent(agents, "p:2"), agents[1])
        self.assertIsNone(watch.find_agent(agents, "zzz"))


class Loop(unittest.TestCase):
    def run_loop(self, watcher: watch.Watcher, first: bool = False) -> tuple[int, str]:
        out = io.StringIO()
        ticks = {"n": 0.0}

        def clock() -> float:
            return ticks["n"]

        def sleep(sec: float) -> None:
            ticks["n"] += sec

        with contextlib.redirect_stdout(out):
            code = watch.run(watcher, 100, 10, first, sleep=sleep, clock=clock)
        return code, out.getvalue()

    def test_keeps_watching_after_agent_event_and_pr_pending(self) -> None:
        pr_states = iter([raw_pr(statusCheckRollup=[])] * 3 + [raw_pr(state="MERGED")])
        agent = {"name": "a1", "agent_status": "idle", "state_change_seq": 2}
        agent_polls = iter(
            [[{"name": "a1", "agent_status": "working", "state_change_seq": 1}], [agent], [agent], [agent]]
        )
        w = watch.Watcher(
            [7],
            ["a1"],
            {"merged"},
            fetch_pr=lambda _n: next(pr_states),
            fetch_agent_list=lambda: next(agent_polls),
        )
        code, out = self.run_loop(w)
        self.assertEqual(code, 0)
        self.assertIn("PR 7 status state=OPEN merge=CLEAN checks=pending", out)
        self.assertNotIn("check-failed", out)
        self.assertIn("AGENT a1 working->idle", out)
        self.assertIn("DONE PR 7 merged", out)

    def test_timeout_names_remaining_targets(self) -> None:
        w = watch.Watcher([7], [], {"merged"}, fetch_pr=lambda _n: raw_pr())
        code, out = self.run_loop(w)
        self.assertEqual(code, watch.EXIT_TIMEOUT)
        self.assertIn("TIMEOUT PR 7", out)

    def test_non_terminal_match_stays_watched_and_survives_restart(self) -> None:
        """A review wakes a first-event run, but the PR is still watched on restart."""
        review = raw_pr(reviews=[{"id": 1, "author": {"login": "bot"}, "state": "COMMENTED"}])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            first = watch.Watcher([7], [], {"review"}, state_path=path, fetch_pr=lambda _n: raw_pr())
            with contextlib.redirect_stdout(io.StringIO()):
                first.poll()
            second = watch.Watcher([7], [], {"review"}, state_path=path, fetch_pr=lambda _n: review)
            code, out = self.run_loop(second, first=True)
            self.assertEqual(code, 0)
            self.assertIn("PR 7 review bot COMMENTED", out)
            self.assertNotIn("ALL DONE", out)
            self.assertNotIn("DONE PR 7", out)
            third = watch.Watcher([7], [], {"review"}, state_path=path, fetch_pr=lambda _n: review)
            self.assertEqual(third.active_prs(), [7])
            self.assertFalse(third.finished())

    def test_plain_run_does_not_exit_on_non_terminal_match(self) -> None:
        polls = iter([raw_pr(), raw_pr(headRefOid="2222222abc"), raw_pr(state="MERGED")])
        w = watch.Watcher([7], [], {"push"}, fetch_pr=lambda _n: next(polls))
        code, out = self.run_loop(w)
        self.assertEqual(code, 0)
        self.assertIn("PR 7 push 2222222", out)
        self.assertIn("DONE PR 7 merged", out)

    def test_merge_and_close_are_terminal_whatever_until_says(self) -> None:
        for state in ("MERGED", "CLOSED"):
            w = watch.Watcher([7], [], {"label:x"}, fetch_pr=lambda _n, s=state: raw_pr(state=s))
            code, out = self.run_loop(w)
            self.assertEqual(code, 0, state)
            self.assertIn(f"DONE PR 7 {state.lower()}", out)

    def test_exit_on_first_event_ignores_events_outside_until(self) -> None:
        polls = iter([raw_pr(), raw_pr(headRefOid="2222222abc"), raw_pr(state="MERGED")])
        w = watch.Watcher([7], [], {"review"}, fetch_pr=lambda _n: next(polls))
        code, out = self.run_loop(w, first=True)
        self.assertEqual(code, 0)
        self.assertIn("PR 7 push 2222222", out)
        self.assertIn("DONE PR 7 merged", out)

    def test_poll_error_is_not_an_event_until_it_repeats(self) -> None:
        def boom(_n: int) -> dict[str, Any]:
            raise watch.WatchError("net down")

        w = watch.Watcher([7], [], {"merged"}, fetch_pr=boom)
        with contextlib.redirect_stderr(io.StringIO()):
            for _ in range(watch.MAX_FAILURES - 1):
                self.assertEqual(w.poll(), 0)
        code, out = self.run_loop(w)
        self.assertEqual(code, watch.EXIT_REPEATED_FAILURE)
        self.assertIn("FATAL PR 7 failed", out)

    def test_fatal_error_exits_with_its_code(self) -> None:
        def no_gh(_n: int) -> dict[str, Any]:
            raise watch.WatchError("gh is not installed", watch.EXIT_MISSING_BINARY)

        code, out = self.run_loop(watch.Watcher([7], [], {"merged"}, fetch_pr=no_gh))
        self.assertEqual(code, watch.EXIT_MISSING_BINARY)
        self.assertIn("FATAL gh is not installed", out)

    def test_agent_missing_on_first_poll_is_an_error(self) -> None:
        w = watch.Watcher([], ["typo"], {"merged"}, fetch_agent_list=lambda: [{"name": "real"}])
        code, out = self.run_loop(w)
        self.assertEqual(code, watch.EXIT_AGENT_NOT_FOUND)
        self.assertIn("FATAL agent 'typo' not found", out)
        self.assertNotIn("ALL DONE", out)

    def test_agent_that_disappears_later_is_done(self) -> None:
        polls = iter([[{"name": "a", "agent_status": "working"}], []])
        w = watch.Watcher([], ["a"], {"merged"}, fetch_agent_list=lambda: next(polls))
        code, out = self.run_loop(w)
        self.assertEqual(code, 0)
        self.assertIn("AGENT a gone", out)
        self.assertIn("ALL DONE", out)

    def test_state_file_carries_events_across_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            first = watch.Watcher([7], [], {"check-failed"}, state_path=path, fetch_pr=lambda _n: raw_pr())
            with contextlib.redirect_stdout(io.StringIO()):
                first.poll()
            fail = raw_pr(statusCheckRollup=[check("a", conclusion="FAILURE")])
            second = watch.Watcher([7], [], {"check-failed"}, state_path=path, fetch_pr=lambda _n: fail)
            code, out = self.run_loop(second, first=True)
            self.assertEqual(code, 0)
            self.assertIn("PR 7 check-failed a", out)
            third = watch.Watcher([7], [], {"check-failed"}, state_path=path, fetch_pr=lambda _n: fail)
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                third.poll()
            self.assertNotIn("check-failed", buf.getvalue())


class StateAndArgs(unittest.TestCase):
    def load(self, content: str) -> watch.Snap:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return watch.Watcher([7], [], {"merged"}, state_path=path, fetch_pr=lambda _n: raw_pr()).state

    def test_incomplete_or_wrong_shaped_state_is_merged_into_empty(self) -> None:
        for content in ("{}", "[]", '"x"', json.dumps({"repo": None, "done": []}), "not json"):
            with contextlib.redirect_stderr(io.StringIO()):
                state = self.load(content)
            for key in ("prs", "agents", "done", "seen_failures"):
                self.assertIsInstance(state[key], dict, content)

    def test_state_for_another_repo_is_ignored(self) -> None:
        state = self.load(json.dumps({"repo": "other/repo", "done": {"pr:7": "merged"}}))
        self.assertEqual(state["done"], {})

    def test_until_validation(self) -> None:
        self.assertEqual(watch.parse_until("review, label:x"), {"review", "label:x"})
        for bad in ("merged,nonsense", "", " , ", "label:"):
            with self.assertRaises(SystemExit, msg=bad):
                watch.parse_until(bad)


if __name__ == "__main__":
    unittest.main()
