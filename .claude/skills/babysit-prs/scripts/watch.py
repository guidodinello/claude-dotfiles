#!/usr/bin/env python3
"""Durable watcher for PRs and herdr agents: one line per event, re-arms itself.

usage: watch.py [-R OWNER/REPO] [--pr N ...] [--agent NAME|PANE_ID ...]
                [--until COND,...] [--timeout MIN] [--interval SEC]
                [--exit-on-first-event] [--state FILE] [--pidfile FILE]

Targets
  --pr N       a pull request (needs -R unless the cwd's remote is the repo)
  --agent ID   a herdr agent, matched by its name or pane id; reported under ID

Events (one line each, "HH:MM:SS KIND TARGET text")
  PR N status ...        first poll only: current state, never an event
  PR N review|comment|label|push|dirty|check-failed|checks|merged|closed ...
  AGENT ID status ...    first poll only
  AGENT ID a->b          agent_status changed
  AGENT ID completed s   completion_seq (or state_change_seq) advanced with the status
                         unchanged: a short working->idle->working blip between polls
  AGENT ID gone          the agent no longer exists
  DONE PR N <cond>       a --until condition matched; that PR is no longer watched
  ALL DONE | TIMEOUT ... the watcher exits (0 and 124)

Idle is an event, never completion: an idle pane can still be waiting on its own
sub-agents. Completion for a PR is whatever --until says. Allowed conditions:
merged closed review comment label label:NAME check-failed dirty push
(default: merged,closed). Exit 0 when every PR is DONE (agents only: when every
agent is gone), 124 on timeout.

Check rules: no checks reported yet, queued, in progress and cancelled are pending,
never failure. An UNKNOWN mergeStateStatus keeps the last known value. A failure is
reported once per (check, head sha), also across restarts when --state is given.

--exit-on-first-event exits 0 after the tick that printed the first event, for the
run_in_background pattern: the caller is notified, handles it, restarts the watcher.
Pair it with --state FILE: the watcher then diffs against the last snapshot instead of
taking a fresh baseline, so nothing that happened between runs is lost.

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

PR_FIELDS = "state,mergeStateStatus,labels,reviews,comments,statusCheckRollup,headRefOid"
FAILED_CONCLUSIONS = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED"}
FAILED_STATES = {"FAILURE", "ERROR"}
PENDING_STATES = {"PENDING", "EXPECTED"}
BASE_UNTIL = {"merged", "closed", "review", "comment", "label", "check-failed", "dirty", "push"}
TERMINAL = {"MERGED", "CLOSED"}


class WatchError(Exception):
    """A gh/herdr call failed; the tick is skipped, nothing is reported."""


# --- pure logic -----------------------------------------------------------


def classify_checks(rollup):
    """Return (aggregate, failed check names). aggregate: pending|passing|failing."""
    failed, pending = [], False
    for c in rollup or []:
        if c.get("__typename") == "StatusContext" or "state" in c and not c.get("status"):
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


def normalize_pr(raw, prev=None):
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
            str(r["id"]): "%s %s" % ((r.get("author") or {}).get("login", "?"), r.get("state", "?"))
            for r in raw.get("reviews") or []
        },
        "comments": {
            str(c["id"]): (c.get("author") or {}).get("login", "?") for c in raw.get("comments") or []
        },
        "head": (raw.get("headRefOid") or "")[:7],
        "checks": checks,
        "failed": failed,
    }


def describe_pr(snap):
    return "state=%s merge=%s checks=%s labels=%s head=%s" % (
        snap["state"],
        snap["merge"],
        snap["checks"],
        ",".join(snap["labels"]) or "-",
        snap["head"] or "-",
    )


def failure_key(name, head):
    return "%s@%s" % (name, head)


def diff_pr(prev, cur, seen_failures):
    """Events as (conds, text) between two snapshots; mutates seen_failures.

    prev None is a baseline: no events except an already terminal state. Failures
    present at baseline are recorded as seen, so they are never reported later.
    """
    events = []
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


def match_until(events, until):
    """The first condition of `until` that any event satisfies, else None."""
    for conds, _ in events:
        hit = sorted(conds & until)
        if hit:
            return hit[0]
    return None


def agent_snapshot(record):
    if record is None:
        return {"present": False, "status": "gone", "sc": 0, "cs": 0}
    return {
        "present": True,
        "status": record.get("agent_status", "unknown"),
        "sc": record.get("state_change_seq", 0),
        "cs": record.get("completion_seq", 0),
    }


def find_agent(agents, ident):
    for a in agents:
        if ident in (a.get("name"), a.get("pane_id"), a.get("terminal_id")):
            return a
    return None


def diff_agents(prev, cur):
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
        return ["%s->%s" % (prev["status"], cur["status"])]
    if cur["cs"] > prev["cs"]:
        return ["completed " + cur["status"]]
    if cur["sc"] > prev["sc"]:
        return ["state changed, still " + cur["status"]]
    return []


# --- IO -------------------------------------------------------------------


def run_json(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WatchError("%s: %s" % (cmd[0], exc)) from exc
    if res.returncode != 0:
        raise WatchError("%s exited %d: %s" % (" ".join(cmd[:3]), res.returncode, res.stderr.strip()[:200]))
    try:
        return json.loads(res.stdout)
    except ValueError as exc:
        raise WatchError("%s: bad JSON" % cmd[0]) from exc


def make_fetch_pr(repo):
    def fetch(number):
        cmd = ["gh", "pr", "view", str(number), "--json", PR_FIELDS]
        if repo:
            cmd += ["-R", repo]
        return run_json(cmd)

    return fetch


def fetch_agents():
    return run_json(["herdr", "agent", "list"])["result"]["agents"]


def emit(kind, target, text):
    print("%s %s %s %s" % (time.strftime("%H:%M:%S"), kind, target, text), flush=True)


def warn(text):
    print("%s WARN %s" % (time.strftime("%H:%M:%S"), text), file=sys.stderr, flush=True)


# --- watcher --------------------------------------------------------------


class Watcher:
    def __init__(self, prs, agents, until, repo=None, state_path=None, fetch_pr=None, fetch_agent_list=None):
        self.prs, self.agents, self.until, self.repo = prs, agents, until, repo
        self.state_path = state_path
        self.fetch_pr = fetch_pr or make_fetch_pr(repo)
        self.fetch_agent_list = fetch_agent_list or fetch_agents
        self.state = self.load_state()

    def load_state(self):
        empty = {"repo": self.repo, "prs": {}, "agents": {}, "done": {}, "seen_failures": {}}
        if not self.state_path or not os.path.exists(self.state_path):
            return empty
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError):
            warn("ignoring unreadable state file %s" % self.state_path)
            return empty
        return state if state.get("repo") == self.repo else empty

    def save_state(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.state, fh)
        os.replace(tmp, self.state_path)

    def active_prs(self):
        return [n for n in self.prs if "pr:%d" % n not in self.state["done"]]

    def active_agents(self):
        return [a for a in self.agents if "agent:" + a not in self.state["done"]]

    def finished(self):
        if self.prs:
            return not self.active_prs()
        return bool(self.agents) and not self.active_agents()

    def poll_pr(self, number):
        key = str(number)
        try:
            raw = self.fetch_pr(number)
        except WatchError as exc:
            warn("PR %s: %s" % (number, exc))
            return 0
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
        hit = match_until(events, self.until)
        if hit:
            self.state["done"]["pr:%d" % number] = hit
            emit("DONE", "PR %d" % number, hit)
        return len(events)

    def poll_agents(self):
        try:
            records = self.fetch_agent_list()
        except (WatchError, KeyError) as exc:
            warn("herdr agent list: %s" % exc)
            return 0
        count = 0
        for ident in self.active_agents():
            cur = agent_snapshot(find_agent(records, ident))
            prev = self.state["agents"].get(ident)
            self.state["agents"][ident] = cur
            if prev is None:
                if cur["present"]:
                    emit("AGENT", ident, "status " + cur["status"])
                else:
                    emit("AGENT", ident, "not found")
                    self.state["done"]["agent:" + ident] = "gone"
                    count += 1
                continue
            for text in diff_agents(prev, cur):
                emit("AGENT", ident, text)
                count += 1
                if text == "gone":
                    self.state["done"]["agent:" + ident] = "gone"
        return count

    def poll(self):
        """One tick over every active target. Returns the number of events printed."""
        count = sum(self.poll_pr(n) for n in self.active_prs())
        if self.agents and self.active_agents():
            count += self.poll_agents()
        self.save_state()
        return count


def run(watcher, timeout_s, interval, exit_on_first_event, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout_s
    while True:
        events = watcher.poll()
        if watcher.finished():
            print("%s ALL DONE" % time.strftime("%H:%M:%S"), flush=True)
            return 0
        if exit_on_first_event and events:
            return 0
        if clock() + interval > deadline:
            left = ["PR %d" % n for n in watcher.active_prs()] + watcher.active_agents()
            print("%s TIMEOUT %s" % (time.strftime("%H:%M:%S"), " ".join(left)), flush=True)
            return 124
        sleep(interval)


def parse_until(text):
    until = set()
    for item in text.split(","):
        item = item.strip()
        if item in BASE_UNTIL or (item.startswith("label:") and len(item) > 6):
            until.add(item)
        elif item:
            raise SystemExit("unknown --until condition: %r" % item)
    return until


def main(argv=None):
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

    if args.pidfile:
        with open(args.pidfile, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))

        def cleanup():
            try:
                os.remove(args.pidfile)
            except OSError:
                pass

        atexit.register(cleanup)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    watcher = Watcher(args.pr, args.agent, parse_until(args.until), args.repo, args.state)
    return run(watcher, args.timeout * 60, args.interval, args.exit_on_first_event)


if __name__ == "__main__":
    sys.exit(main())
