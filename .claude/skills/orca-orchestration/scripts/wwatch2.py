#!/usr/bin/env python3
"""Block until one of several workers needs the orchestrator, then print why and exit.

usage: wwatch2.py [--follow] [--pidfile FILE] <max-minutes> <worktree-path | transcript-dir-name>...

Default (one-shot): prints the events of the first poll that has any (usually one) and exits. Run it with run_in_background and restart
it after each event.
--follow: keeps watching and prints one flushed line per event, each reported once. Run it
under the Monitor tool (every stdout line is a notification; a background Bash only
notifies when the process exits). It ends on TIMEOUT or when every worker is DEAD.
--pidfile FILE: write the pid there; stop it with kill "$(cat FILE)", never pkill -f.

Events, one line each:
  READY <worker> <tool>     a plan (ExitPlanMode) or question (AskUserQuestion) is pending
  PR <worker> [urls]        the worker's own `gh pr create` printed a new PR URL. A URL
                            that only appears in text (a reviewer's transcript) does not count
  IDLE <worker> age <s>     no transcript write for WWATCH_IDLE_SECS and nothing pending
  STUCK:<tool> <worker> ... a tool pending that long (a pending Bash, or a parent waiting
                            on a subagent, gets WWATCH_BASH_SECS instead)
  NOTRANSCRIPT <worker>     still no transcript after WWATCH_IDLE_SECS
  DEAD <worker>             no live claude process has the worker's worktree as its cwd
  TIMEOUT                   max-minutes passed

Dedup under --follow: READY once per pending tool id; PR once per URL; IDLE and STUCK once
until the transcript is written again or a new tool is pending; NOTRANSCRIPT once; DEAD once
per death (a worker seen alive again can die again).

A plan or question that is already pending when the watcher starts is reported only
after WWATCH_GRACE_SECS: a watcher started right after sending an approval would
otherwise read the still-unanswered ExitPlanMode and report READY at once. A new
plan or question (a different tool id) is reported immediately.
Permission prompts do not show in the transcript: a STUCK on an MCP tool usually is one.

DEAD comes from the process table (ps + lsof), because a killed session leaves no
marker in its transcript: the rows before an Orca restart end like an idle turn. It needs
two polls in a row. Accepted limit: another claude session (a reviewer) running in the
same worktree keeps a dead worker looking alive.
"""
import argparse
import atexit
import importlib.util
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "_transcript", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_transcript.py")
)
tx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tx)

WAITING = ("ExitPlanMode", "AskUserQuestion")
CLAUDE_COMMAND = re.compile(r"^(\S*/)?claude( |$)")
DEAD_POLLS = 2


@dataclass(frozen=True, slots=True)
class Limits:
    idle: int = int(os.environ.get("WWATCH_IDLE_SECS", 240))
    bash: int = int(os.environ.get("WWATCH_BASH_SECS", 900))
    grace: int = int(os.environ.get("WWATCH_GRACE_SECS", 90))


@dataclass(slots=True)
class Memory:
    """What the watcher already told the orchestrator about one worker."""

    base_wait: str | None = None
    ready_id: str | None = None
    prs_seen: set[str] = field(default_factory=set)
    idle_key: tuple | None = None
    dead_polls: int = 0
    dead_reported: bool = False
    no_transcript_reported: bool = False


def waiting_id(snap):
    p = snap["pending"] if snap else None
    return p.get("id") if p and p.get("name") in WAITING else None


def snapshot(project):
    transcript = tx.latest(project)
    if not transcript:
        return None
    pending, text, _ = tx.state(transcript)
    main_m = os.path.getmtime(transcript)
    sub_m = tx.subagent_mtime(transcript)
    return {
        "age": time.time() - max(main_m, sub_m),
        "stamp": max(main_m, sub_m),
        "via_sub": sub_m > main_m,
        "pending": pending,
        "text": text,
        "prs": tx.own_pr_urls(transcript),
    }


def claude_pids(ps_output):
    """Pids of the processes whose command is the claude binary, from `ps -axo pid=,command=`."""
    pids = []
    for line in ps_output.splitlines():
        pid, _, command = line.strip().partition(" ")
        if pid.isdigit() and CLAUDE_COMMAND.match(command.strip()):
            pids.append(pid)
    return pids


def live_cwds():
    """Real cwds of every running claude process, or None when the probe is unavailable.

    Uses ps, not pgrep: macOS pgrep skips its own ancestors, so a watcher could not see the
    session it runs under.
    """
    try:
        ps = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10)
        if ps.returncode != 0:
            return None
        pids = claude_pids(ps.stdout)
        if not pids:
            return set()
        lsof = subprocess.run(
            ["lsof", "-a", "-p", ",".join(pids), "-d", "cwd", "-Fn"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    cwds = {os.path.realpath(line[1:]) for line in lsof.stdout.splitlines() if line.startswith("n")}
    # Live claude processes always have a cwd: no answer at all means lsof failed, not that they are gone.
    return cwds or None


def worker_cwd(worker, project):
    looks_like_path = os.sep in worker or worker.startswith("~") or os.path.isdir(worker)
    if looks_like_path:
        return os.path.realpath(os.path.expanduser(worker))
    cwd = tx.first_cwd(project)
    return os.path.realpath(cwd) if cwd else None


def detect(w, project, snap, mem, elapsed, alive, limits):
    """New events for one worker as (line, tail) pairs, updating `mem`. `alive` is True,
    False, or None when unknown."""
    events = []
    started = snap is not None or elapsed > limits.idle
    mem.dead_polls = mem.dead_polls + 1 if alive is False and started else 0
    if alive is True:
        mem.dead_reported = False  # relaunched (claude --resume): a second death is a new event
    if mem.dead_polls >= DEAD_POLLS and not mem.dead_reported:
        mem.dead_reported = True
        events.append((f"DEAD {w} no live claude process in its worktree", ""))
    if snap is None:
        if elapsed > limits.idle and not mem.no_transcript_reported:
            mem.no_transcript_reported = True
            events.append((f"NOTRANSCRIPT {w} {project}", ""))
        return events
    p = snap["pending"]
    pid = p.get("id") if p else None
    waiting = bool(p) and p.get("name") in WAITING
    if waiting and pid != mem.ready_id and (pid != mem.base_wait or elapsed > limits.grace):
        mem.ready_id = pid
        events.append((f"READY {w} {p.get('name')}", ""))
    new_prs = [u for u in snap["prs"] if u not in mem.prs_seen]
    if new_prs:
        mem.prs_seen.update(new_prs)
        events.append((f"PR {w} {new_prs}", ""))
    limit = limits.bash if (p and p.get("name") == "Bash") or snap["via_sub"] else limits.idle
    key = (snap["stamp"], pid)
    # A worker waiting on the orchestrator is not stuck: READY already said so.
    if not waiting and snap["age"] > limit and elapsed > limits.idle and key != mem.idle_key:
        mem.idle_key = key
        kind = "IDLE" if not p else "STUCK:" + p.get("name", "?")
        events.append((f"{kind} {w} age {int(snap['age'])}", snap["text"][-800:]))
    return events


def say(text):
    print(text, flush=True)


def run(
    workers, max_minutes, follow, *, projects, probe=live_cwds, limits=None, poll=None,
    clock=time.time, sleep=time.sleep, out=say, snap_fn=snapshot,
):
    limits = limits or Limits()
    poll = float(os.environ.get("WWATCH_POLL_SECS", 30)) if poll is None else poll
    start = clock()
    mems = {}
    for w in workers:
        s = snap_fn(projects[w])
        mems[w] = Memory(base_wait=waiting_id(s), prs_seen=set(s["prs"]) if s else set())
    cwds = {}
    while clock() - start < max_minutes * 60:
        elapsed = clock() - start
        live = probe()
        batch = []
        for w in workers:
            if cwds.get(w) is None:
                cwds[w] = worker_cwd(w, projects[w])
            alive = None if live is None or cwds[w] is None else cwds[w] in live
            batch += detect(w, projects[w], snap_fn(projects[w]), mems[w], elapsed, alive, limits)
        for line, tail in batch:
            out(line)
            if tail:
                out(tail)
        if batch and not follow:
            return 0
        if follow and all(m.dead_reported for m in mems.values()):
            return 0
        sleep(poll)
    out("TIMEOUT")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--pidfile", metavar="FILE")
    ap.add_argument("max_minutes", type=float)
    ap.add_argument("workers", nargs="+")
    args = ap.parse_args(argv)
    if args.pidfile:
        # atexit does not run on the default SIGTERM: turn it into a normal exit so kill removes the pidfile.
        # Installed before the file exists, so a pidfile on disk means the handler is already in place.
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(128 + signal.SIGTERM))
        with open(args.pidfile, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        atexit.register(lambda: os.path.exists(args.pidfile) and os.remove(args.pidfile))
    projects = {w: tx.resolve(w) for w in args.workers}
    return run(args.workers, args.max_minutes, args.follow, projects=projects)


if __name__ == "__main__":
    sys.exit(main())
