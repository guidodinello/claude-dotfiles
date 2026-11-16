#!/usr/bin/env python3
"""Durable watcher for PRs and herdr agents: one line per event, re-arms itself.

usage: watch.py [-R OWNER/REPO] [--pr N ...] [--agent NAME|PANE_ID ...]
                [--until COND,...] [--timeout MIN] [--interval SEC]
                [--exit-on-first-event] [--state FILE] [--pidfile FILE]

Targets
  --pr N       a pull request (needs -R unless the cwd's remote is the repo)
  --agent ID   a herdr agent, matched by its name or pane id; reported under ID.
               An ID that matches no agent on the first poll is an error (exit 6).

Events (one line each, "HH:MM:SS KIND TARGET text")
  PR N status ...        first poll only: current state, never an event
  PR N review|comment|label|push|dirty|check-failed|checks|merged|closed ...
  AGENT ID status ...    first poll only
  AGENT ID a->b          agent_status changed
  AGENT ID completed s   completion_seq advanced with the status unchanged: a short
                         working->idle->working blip between two polls
  AGENT ID state changed, still s
                         only state_change_seq advanced (same blip, no completion)
  AGENT ID gone          the agent no longer exists
  DONE PR N merged|closed
                         the PR reached a terminal state and is no longer watched
  ALL DONE | TIMEOUT ... the watcher exits (0 and 124)

Terminal states: a PR is done only when it is merged or closed, whatever --until
says; an agent is done only when it is gone. Every other event, matched by --until or
not, leaves its target watched.

--until (default merged,closed; merged and closed are always added, an empty value is
rejected) picks which PR events wake an --exit-on-first-event run: merged closed
review comment label label:NAME check-failed dirty push. A PR event outside --until
is still printed, but does not end such a run. Every agent event wakes it.

Idle is an event, never completion: an idle pane can still be waiting on its own
sub-agents. Confirm a review or a fix from the PR (--until review, label:reviewed).

Check rules: no checks reported yet, queued, in progress and cancelled are pending,
never failure. An UNKNOWN mergeStateStatus keeps the last known value. A failure is
reported once per (check, head sha), also across restarts when --state is given.

Exit codes
  0    every PR is merged or closed (agents only: every agent is gone), printed as
       ALL DONE; OR, with --exit-on-first-event, the first wake event. In that mode
       exit 0 alone does not mean "finished": read the lines for ALL DONE.
  124  timeout
  3    gh or herdr is not installed
  4    gh is not authenticated
  5    the same target failed 5 polls in a row (wrong --pr or -R, network, bad JSON)
  6    an --agent matched nothing on the first poll
  Codes 3-6 print a FATAL line instead of polling until the timeout.

--exit-on-first-event is for the run_in_background pattern: the caller is notified,
handles the event, restarts the watcher. Pair it with --state FILE: the watcher then
diffs against the last snapshot instead of taking a fresh baseline, so nothing that
happened between runs is lost.

Stop a background watcher with: kill "$(cat PIDFILE)"  (--pidfile). Never pkill -f.
"""

import argparse
import atexit
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

PR_FIELDS = "state,mergeStateStatus,labels,reviews,comments,statusCheckRollup,headRefOid"
FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED"}
FAILED_STATES = {"FAILURE", "ERROR"}
PENDING_STATES = {"PENDING", "EXPECTED"}
BASE_UNTIL = {"merged", "closed", "review", "comment", "label", "check-failed", "dirty", "push"}
TERMINAL = {"MERGED", "CLOSED"}
TERMINAL_CONDS = {"merged", "closed"}
AUTH_MARKERS = ("gh auth login", "not logged in", "http 401", "bad credentials", "authentication")
MAX_FAILURES = 5

EXIT_TIMEOUT = 124
EXIT_MISSING_BINARY = 3
EXIT_AUTH = 4
EXIT_REPEATED_FAILURE = 5
EXIT_AGENT_NOT_FOUND = 6

Snap = dict[str, Any]
Event = tuple[set[str], str]


class WatchError(Exception):
    """A gh/herdr call failed. With code != 0 the failure is fatal: exit with that code."""

    def __init__(self, message: str, code: int = 0) -> None:
        super().__init__(message)
        self.code = code


# --- pure logic -----------------------------------------------------------


def classify_checks(rollup: list[dict[str, Any]] | None) -> tuple[str, list[str]]:
    """Return (aggregate, failed check names). aggregate: pending|passing|failing."""
    failed: list[str] = []
    pending = False
    for c in rollup or []:
        is_status_context = c.get("__typename") == "StatusContext" or (
            "state" in c and not c.get("status")
        )
        if is_status_context:
            state = (c.get("state") or "").upper()
            if state in FAILED_STATES:
                failed.append(c.get("context") or c.get("name") or "?")
            elif state in PENDING_STATES or not state:
                pending = True
            continue
        status = (c.get("status") or "").upper()
        conclusion = (c.get("conclusion") or "").upper()
        if status != "COMPLETED" or not conclusion or conclusion == "CANCELLED":
            pending = True
        elif conclusion in FAILED_CONCLUSIONS:
            failed.append(c.get("name") or "?")
    if failed:
        return "failing", failed
    return ("pending" if pending or not rollup else "passing"), []


def normalize_pr(raw: dict[str, Any], prev: Snap | None = None) -> Snap:
    """Reduce a `gh pr view --json` payload to the snapshot we diff."""
    checks, failed = classify_checks(raw.get("statusCheckRollup"))
    merge = raw.get("mergeStateStatus") or "UNKNOWN"
    if merge == "UNKNOWN" and prev:
        merge = prev.get("merge", "UNKNOWN")
    return {
        "state": raw.get("state", "?"),
        "merge": merge,
        "labels": sorted(label["name"] for label in raw.get("labels") or []),
        "reviews": {
            str(r["id"]): "{} {}".format((r.get("author") or {}).get("login", "?"), r.get("state", "?"))
            for r in raw.get("reviews") or []
        },
        "comments": {
            str(c["id"]): (c.get("author") or {}).get("login", "?") for c in raw.get("comments") or []
        },
        "head": (raw.get("headRefOid") or "")[:7],
        "checks": checks,
        "failed": failed,
    }


def describe_pr(snap: Snap) -> str:
    return "state={} merge={} checks={} labels={} head={}".format(
        snap["state"],
        snap["merge"],
        snap["checks"],
        ",".join(snap["labels"]) or "-",
        snap["head"] or "-",
    )


def failure_key(name: str, head: str) -> str:
    return f"{name}@{head}"


def diff_pr(prev: Snap | None, cur: Snap, seen_failures: set[str]) -> list[Event]:
    """Events as (conds, text) between two snapshots; mutates seen_failures.

    prev None is a baseline: no events except an already terminal state. Failures
    present at baseline are recorded as seen, so they are never reported later.
    """
    events: list[Event] = []
    if prev is None:
        for name in cur["failed"]:
            seen_failures.add(failure_key(name, cur["head"]))
        if cur["state"] in TERMINAL:
            events.append(({cur["state"].lower()}, cur["state"].lower()))
        return events
    if cur["state"] != prev["state"] and cur["state"] in TERMINAL:
        events.append(({cur["state"].lower()}, cur["state"].lower()))
    for rid, text in cur["reviews"].items():
        if rid not in prev["reviews"]:
            events.append(({"review"}, "review " + text))
    for cid, author in cur["comments"].items():
        if cid not in prev["comments"]:
            events.append(({"comment"}, "comment " + author))
    for name in sorted(set(cur["labels"]) - set(prev["labels"])):
        events.append(({"label", "label:" + name}, "label +" + name))
    for name in sorted(set(prev["labels"]) - set(cur["labels"])):
        events.append(({"label"}, "label -" + name))
    if cur["head"] != prev["head"]:
        events.append(({"push"}, "push " + cur["head"]))
    if cur["merge"] == "DIRTY" and prev["merge"] != "DIRTY":
        events.append(({"dirty"}, "dirty (merge conflict)"))
    for name in cur["failed"]:
        key = failure_key(name, cur["head"])
        if key not in seen_failures:
            seen_failures.add(key)
            events.append(({"check-failed"}, "check-failed " + name))
    if cur["checks"] != prev["checks"]:
        events.append((set(), "checks " + cur["checks"]))
    return events


def terminal_hit(events: list[Event]) -> str | None:
    """'merged' or 'closed' when an event says the PR reached a terminal state."""
    for conds, _ in events:
        hit = sorted(conds & TERMINAL_CONDS)
        if hit:
            return hit[0]
    return None


def count_wake(events: list[Event], until: set[str]) -> int:
    """How many events satisfy a condition of `until`."""
    return sum(1 for conds, _ in events if conds & until)


def agent_snapshot(record: dict[str, Any] | None) -> Snap:
    if record is None:
        return {"present": False, "status": "gone", "sc": 0, "cs": 0}
    return {
        "present": True,
        "status": record.get("agent_status", "unknown"),
        "sc": record.get("state_change_seq", 0),
        "cs": record.get("completion_seq", 0),
    }


def find_agent(agents: list[dict[str, Any]], ident: str) -> dict[str, Any] | None:
    for a in agents:
        if ident in (a.get("name"), a.get("pane_id"), a.get("terminal_id")):
            return a
    return None


def diff_agents(prev: Snap | None, cur: Snap) -> list[str]:
    """Events as text. cur/prev are agent_snapshot dicts; prev None is a baseline."""
    if prev is None:
        return []
    if prev["present"] and not cur["present"]:
        return ["gone"]
    if not prev["present"] and cur["present"]:
        return ["appeared " + cur["status"]]
    if not cur["present"]:
        return []
    if cur["status"] != prev["status"]:
        return [f"{prev['status']}->{cur['status']}"]
    if cur["cs"] > prev["cs"]:
        return ["completed " + cur["status"]]
    if cur["sc"] > prev["sc"]:
        return ["state changed, still " + cur["status"]]
    return []


# --- IO -------------------------------------------------------------------


def run_json(cmd: list[str]) -> Any:
    """Run a command and parse its JSON. Missing binary and auth failure are fatal."""
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except FileNotFoundError as exc:
        raise WatchError(f"{cmd[0]} is not installed", EXIT_MISSING_BINARY) from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WatchError(f"{cmd[0]}: {exc}") from exc
    if res.returncode != 0:
        err = res.stderr.strip()
        code = EXIT_AUTH if any(m in err.lower() for m in AUTH_MARKERS) else 0
        raise WatchError(f"{' '.join(cmd[:3])} exited {res.returncode}: {err[:200]}", code)
    try:
        return json.loads(res.stdout)
    except ValueError as exc:
        raise WatchError(f"{cmd[0]}: bad JSON") from exc


def make_fetch_pr(repo: str | None) -> Callable[[int], dict[str, Any]]:
    def fetch(number: int) -> dict[str, Any]:
        cmd = ["gh", "pr", "view", str(number), "--json", PR_FIELDS]
        if repo:
            cmd += ["-R", repo]
        return run_json(cmd)

    return fetch


def fetch_agents() -> list[dict[str, Any]]:
    payload = run_json(["herdr", "agent", "list"])
    try:
        return payload["result"]["agents"]
    except (KeyError, TypeError) as exc:
        raise WatchError("herdr agent list: unexpected JSON shape") from exc


def emit(kind: str, target: object, text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {kind} {target} {text}", flush=True)


def warn(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} WARN {text}", file=sys.stderr, flush=True)


# --- watcher --------------------------------------------------------------


class Watcher:
    def __init__(
        self,
        prs: list[int],
        agents: list[str],
        until: set[str],
        repo: str | None = None,
        state_path: str | None = None,
        fetch_pr: Callable[[int], dict[str, Any]] | None = None,
        fetch_agent_list: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.prs, self.agents, self.repo = prs, agents, repo
        self.until = until | TERMINAL_CONDS
        self.state_path = state_path
        self.fetch_pr = fetch_pr or make_fetch_pr(repo)
        self.fetch_agent_list = fetch_agent_list or fetch_agents
        self.failures: dict[str, int] = {}
        self.state = self.load_state()

    def load_state(self) -> Snap:
        empty: Snap = {"repo": self.repo, "prs": {}, "agents": {}, "done": {}, "seen_failures": {}}
        if not self.state_path or not os.path.exists(self.state_path):
            return empty
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            warn(f"ignoring unreadable state file {self.state_path}")
            return empty
        if not isinstance(loaded, dict) or loaded.get("repo") != self.repo:
            return empty
        for key in ("prs", "agents", "done", "seen_failures"):
            if isinstance(loaded.get(key), dict):
                empty[key] = loaded[key]
        return empty

    def save_state(self) -> None:
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh)
        os.replace(tmp, self.state_path)

    def active_prs(self) -> list[int]:
        return [n for n in self.prs if f"pr:{n}" not in self.state["done"]]

    def active_agents(self) -> list[str]:
        return [a for a in self.agents if f"agent:{a}" not in self.state["done"]]

    def finished(self) -> bool:
        if self.prs:
            return not self.active_prs()
        return bool(self.agents) and not self.active_agents()

    def record_failure(self, target: str, exc: WatchError) -> None:
        """Count a failed poll. Fatal errors, and the Nth in a row, stop the watcher."""
        if exc.code:
            raise exc
        self.failures[target] = self.failures.get(target, 0) + 1
        if self.failures[target] >= MAX_FAILURES:
            raise WatchError(f"{target} failed {MAX_FAILURES} polls in a row: {exc}", EXIT_REPEATED_FAILURE)
        warn(f"{target}: {exc}")

    def poll_pr(self, number: int) -> int:
        """Poll one PR. Returns the number of events that wake a first-event run."""
        key = str(number)
        try:
            raw = self.fetch_pr(number)
        except WatchError as exc:
            self.record_failure(f"PR {number}", exc)
            return 0
        self.failures.pop(f"PR {number}", None)
        prev = self.state["prs"].get(key)
        cur = normalize_pr(raw, prev)
        seen = set(self.state["seen_failures"].get(key, []))
        events = diff_pr(prev, cur, seen)
        self.state["prs"][key] = cur
        self.state["seen_failures"][key] = sorted(seen)
        if prev is None:
            emit("PR", number, "status " + describe_pr(cur))
        for _, text in events:
            emit("PR", number, text)
        terminal = terminal_hit(events)
        if terminal:
            self.state["done"][f"pr:{number}"] = terminal
            emit("DONE", f"PR {number}", terminal)
        return count_wake(events, self.until)

    def poll_agents(self) -> int:
        try:
            records = self.fetch_agent_list()
        except WatchError as exc:
            self.record_failure("herdr agent list", exc)
            return 0
        self.failures.pop("herdr agent list", None)
        count = 0
        for ident in self.active_agents():
            cur = agent_snapshot(find_agent(records, ident))
            prev = self.state["agents"].get(ident)
            if prev is None and not cur["present"]:
                raise WatchError(f"agent {ident!r} not found on the first poll (wrong name or pane id?)", EXIT_AGENT_NOT_FOUND)
            self.state["agents"][ident] = cur
            if prev is None:
                emit("AGENT", ident, "status " + cur["status"])
                continue
            for text in diff_agents(prev, cur):
                emit("AGENT", ident, text)
                count += 1
                if text == "gone":
                    self.state["done"][f"agent:{ident}"] = "gone"
        return count

    def poll(self) -> int:
        """One tick over every active target. Returns the number of wake events."""
        count = sum(self.poll_pr(n) for n in self.active_prs())
        if self.agents and self.active_agents():
            count += self.poll_agents()
        self.save_state()
        return count


def run(
    watcher: Watcher,
    timeout_s: float,
    interval: float,
    exit_on_first_event: bool,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    deadline = clock() + timeout_s
    while True:
        try:
            wake = watcher.poll()
        except WatchError as exc:
            print(f"{time.strftime('%H:%M:%S')} FATAL {exc}", flush=True)
            return exc.code or EXIT_REPEATED_FAILURE
        if watcher.finished():
            print(f"{time.strftime('%H:%M:%S')} ALL DONE", flush=True)
            return 0
        if exit_on_first_event and wake:
            return 0
        if clock() + interval > deadline:
            left = [f"PR {n}" for n in watcher.active_prs()] + watcher.active_agents()
            print(f"{time.strftime('%H:%M:%S')} TIMEOUT {' '.join(left)}", flush=True)
            return EXIT_TIMEOUT
        sleep(interval)


def parse_until(text: str) -> set[str]:
    until: set[str] = set()
    for item in text.split(","):
        item = item.strip()
        if item in BASE_UNTIL or (item.startswith("label:") and len(item) > 6):
            until.add(item)
        elif item:
            raise SystemExit(f"unknown --until condition: {item!r}")
    if not until:
        raise SystemExit("--until needs at least one condition")
    return until


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-R", "--repo", help="OWNER/REPO passed to gh")
    ap.add_argument("--pr", type=int, action="append", default=[], metavar="N")
    ap.add_argument("--agent", action="append", default=[], metavar="ID")
    ap.add_argument("--until", default="merged,closed")
    ap.add_argument("--timeout", type=float, default=60, metavar="MIN")
    ap.add_argument("--interval", type=float, default=30, metavar="SEC")
    ap.add_argument("--exit-on-first-event", action="store_true")
    ap.add_argument("--state", metavar="FILE")
    ap.add_argument("--pidfile", metavar="FILE")
    args = ap.parse_args(argv)
    if not args.pr and not args.agent:
        ap.error("give at least one --pr or --agent")
    until = parse_until(args.until)

    if args.pidfile:
        with open(args.pidfile, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))

        def cleanup() -> None:
            try:
                os.remove(args.pidfile)
            except OSError:
                pass

        atexit.register(cleanup)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    watcher = Watcher(args.pr, args.agent, until, args.repo, args.state)
    return run(watcher, args.timeout * 60, args.interval, args.exit_on_first_event)


if __name__ == "__main__":
    sys.exit(main())
