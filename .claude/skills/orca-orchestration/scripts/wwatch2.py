#!/usr/bin/env python3
"""Block until one of several workers needs the orchestrator, then print why and exit.

usage: wwatch2.py <max-minutes> <worktree-path | transcript-dir-name>...

Exits with one line per event:
  READY <worker> <tool>     a plan (ExitPlanMode) or question (AskUserQuestion) is pending
  PR <worker> [urls]        a new pull request URL appeared in the last text
  IDLE <worker> age <s>     no transcript write for WWATCH_IDLE_SECS and nothing pending
  STUCK:<tool> <worker> ... a tool pending that long (a pending Bash, or a parent waiting
                            on a subagent, gets WWATCH_BASH_SECS instead)
  NOTRANSCRIPT <worker>     still no transcript after WWATCH_IDLE_SECS
  TIMEOUT                   max-minutes passed

A plan or question that is already pending when the watcher starts is reported only
after WWATCH_GRACE_SECS: a watcher started right after sending an approval would
otherwise read the still-unanswered ExitPlanMode and report READY at once. A new
plan or question (a different tool id) is reported immediately.
Permission prompts do not show in the transcript: a STUCK on an MCP tool usually is one.
"""
import importlib.util
import os
import re
import sys
import time

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "_transcript", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_transcript.py")
)
tx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tx)

IDLE = int(os.environ.get("WWATCH_IDLE_SECS", 240))
BASH = int(os.environ.get("WWATCH_BASH_SECS", 900))
GRACE = int(os.environ.get("WWATCH_GRACE_SECS", 90))
POLL = float(os.environ.get("WWATCH_POLL_SECS", 30))
PR_RE = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/pull/\d+")
WAITING = ("ExitPlanMode", "AskUserQuestion")

if len(sys.argv) < 3:
    sys.exit(__doc__.strip())
max_minutes = float(sys.argv[1])
workers = sys.argv[2:]
projects = {w: tx.resolve(w) for w in workers}


def snapshot(w):
    transcript = tx.latest(projects[w])
    if not transcript:
        return None
    pending, text, _ = tx.state(transcript)
    main_m = os.path.getmtime(transcript)
    sub_m = tx.subagent_mtime(transcript)
    return {
        "age": time.time() - max(main_m, sub_m),
        "via_sub": sub_m > main_m,
        "pending": pending,
        "text": text,
    }


start = time.time()
initial = {w: snapshot(w) for w in workers}
base_text = {w: (s["text"] if s else "") for w, s in initial.items()}
base_wait = {
    w: (s["pending"].get("id") if s and s["pending"] and s["pending"].get("name") in WAITING else None)
    for w, s in initial.items()
}

while time.time() - start < max_minutes * 60:
    elapsed = time.time() - start
    for w in workers:
        s = snapshot(w)
        if s is None:
            if elapsed > IDLE:
                print("NOTRANSCRIPT", w, projects[w])
                sys.exit()
            continue
        p = s["pending"]
        if p and p.get("name") in WAITING and (p.get("id") != base_wait[w] or elapsed > GRACE):
            print("READY", w, p.get("name"))
            sys.exit()
        if s["text"] != base_text[w] and PR_RE.search(s["text"]):
            print("PR", w, PR_RE.findall(s["text"]))
            sys.exit()
        limit = BASH if (p and p.get("name") == "Bash") or s["via_sub"] else IDLE
        if s["age"] > limit and elapsed > IDLE:
            print("IDLE" if not p else "STUCK:" + p.get("name", "?"), w, "age", int(s["age"]))
            print(s["text"][-800:])
            sys.exit()
    time.sleep(POLL)
print("TIMEOUT")
