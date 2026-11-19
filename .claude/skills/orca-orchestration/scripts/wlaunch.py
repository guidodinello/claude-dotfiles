#!/usr/bin/env python3
"""Launch one implementer session (a "worker") in an Orca worktree.

usage: wlaunch.py create --repo <selector> --name <worktree-name> --base <ref> --branch <branch>
                         [--comment <text>]
       wlaunch.py code <worktree> --title <tab-title> [--planner <handle>] [--prompt <text>] [--command <cmd>]
       wlaunch.py start <worktree> --title <tab-title> [--prompt <text>] [--command <cmd>]

Two steps, because make-brief.py writes <worktree>/.task-brief.md in between:

  create  orca worktree create (no parent, with the final branch name), prints
          {"worktree": ..., "branch": ...}
  start   needs <worktree>/.task-brief.md. Opens a terminal running Claude Code in plan
          mode, waits until the TUI shows "plan mode on", then sends the one-line prompt.
          Prints {"worktree": ..., "handle": ...} for ids.json.
  code    After the orchestrator read and accepted the plan: saves the pending ExitPlanMode
          plan to <worktree>/.task-plan.md, closes the planner terminal, and starts a fresh
          coder session in auto mode on the plan. The planner's plan is never approved in
          its own session, because approving there starts coding on the planner's model and
          effort. Prints {"worktree": ..., "handle": ...}.

`start` never sends the prompt before "plan mode on" shows, or it would land in the shell.
If the command is still typed at the shell prompt (a slow nvm hook leaves it there), it
presses Enter once and waits again, then fails with the terminal left open for inspection.
"""
import argparse
import importlib.util
import json
import os
import sys
import time

sys.dont_write_bytecode = True
_spec = importlib.util.spec_from_file_location(
    "_orca", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_orca.py")
)
_orca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_orca)
_tspec = importlib.util.spec_from_file_location(
    "_transcript", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_transcript.py")
)
_tx = importlib.util.module_from_spec(_tspec)
_tspec.loader.exec_module(_tx)

# Model and effort per phase: the model-frontier skill's roles.json (worker-plan, worker-code).
DEFAULT_COMMAND = "claude --model opus --effort medium --permission-mode plan"
CODE_COMMAND = "claude --model sonnet --effort high --permission-mode auto"
CODE_PROMPT = (
    "Your plan is approved and saved in .task-plan.md. Read .task-brief.md for the task and its "
    "rules, then implement .task-plan.md without re-planning. When done, open the PR as the brief "
    "specifies (or report back if the brief says there is no PR)."
)
DEFAULT_PROMPT = (
    "Read .task-brief.md in this worktree root and follow it exactly: investigate, then write "
    "your implementation plan with an explicit Open questions section. Do not implement until "
    "the orchestrator approves the plan. When implementation is done, open the PR as the "
    "brief specifies (or report back if the brief says there is no PR)."
)
PLAN_MODE_MARKER = "plan mode on"
AUTO_MODE_MARKER = "auto mode on"
IDLE_TIMEOUT_MS = 120_000
PLAN_WAIT_SECS = float(os.environ.get("WLAUNCH_PLAN_WAIT_SECS", 30))
PLAN_POLL_SECS = float(os.environ.get("WLAUNCH_PLAN_POLL_SECS", 2))


def create(repo, name, base, branch, comment):
    args = ["worktree", "create", "--repo", repo, "--name", name, "--no-parent", "--base-branch", base, "--branch", branch]
    if comment:
        args += ["--comment", comment]
    result = _orca.orca(*args)
    return {"worktree": result["worktree"]["path"], "branch": branch}


def preview(handle):
    return _orca.orca("terminal", "show", "--terminal", handle)["terminal"].get("preview") or ""


def command_at_prompt(text, command):
    """True when the command is on the last non-empty line: still typed, not run or scrolled up."""
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and " ".join(command.split()[:2]) in lines[-1]


def wait_for_mode(handle, marker):
    deadline = time.monotonic() + PLAN_WAIT_SECS
    while True:
        if marker in preview(handle).lower():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(PLAN_POLL_SECS)


def start(worktree, title, prompt, command):
    brief = os.path.join(worktree, ".task-brief.md")
    if not os.path.isfile(brief):
        raise FileNotFoundError(f"{brief} is missing: run make-brief.py first")
    return launch(worktree, title, prompt, command, PLAN_MODE_MARKER)


def save_pending_plan(worktree):
    transcript = _tx.latest(_tx.resolve(worktree))
    if not transcript:
        raise RuntimeError(f"no transcript for {worktree}")
    pending, _, _ = _tx.state(transcript)
    if not pending or pending.get("name") != "ExitPlanMode":
        raise RuntimeError("no plan is pending approval: read it with wplan.py once the planner presents it")
    path = os.path.join(worktree, ".task-plan.md")
    # The worktree is a checkout of someone's repo: a committed .task-plan.md symlink must not
    # redirect this write outside it.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write((pending.get("input") or {}).get("plan") or "")
    return path


def code(worktree, title, planner, prompt, command):
    save_pending_plan(worktree)
    if planner:
        _orca.orca("terminal", "close", "--terminal", planner)
    return launch(worktree, title, prompt, command, AUTO_MODE_MARKER)


def launch(worktree, title, prompt, command, marker):
    result = _orca.orca(
        "terminal", "create", "--worktree", f"path:{worktree}", "--title", title, "--command", command
    )
    handle = result["terminal"]["handle"]
    _orca.orca("terminal", "wait", "--terminal", handle, "--for", "tui-idle", "--timeout-ms", str(IDLE_TIMEOUT_MS))
    if not wait_for_mode(handle, marker):
        if not command_at_prompt(preview(handle), command):
            raise RuntimeError(f"no '{marker}' on {handle} and the command is not at the prompt")
        _orca.orca("terminal", "send", "--terminal", handle, "--text", "", "--enter")
        if not wait_for_mode(handle, marker):
            raise RuntimeError(f"no '{marker}' on {handle} after pressing Enter")
    _orca.send_line(handle, prompt)
    return {"worktree": worktree, "handle": handle}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--repo", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--base", required=True)
    c.add_argument("--branch", required=True)
    c.add_argument("--comment", default="")
    s = sub.add_parser("start")
    s.add_argument("worktree")
    s.add_argument("--title", required=True)
    s.add_argument("--prompt", default=DEFAULT_PROMPT)
    s.add_argument("--command", default=DEFAULT_COMMAND)
    k = sub.add_parser("code")
    k.add_argument("worktree")
    k.add_argument("--title", required=True)
    k.add_argument("--planner", help="the planner's terminal handle, closed before the coder starts")
    k.add_argument("--prompt", default=CODE_PROMPT)
    k.add_argument("--command", default=CODE_COMMAND)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "create":
            out = create(args.repo, args.name, args.base, args.branch, args.comment)
        elif args.cmd == "start":
            _orca.refuse_unsendable(args.prompt)
            out = start(os.path.abspath(args.worktree), args.title, args.prompt, args.command)
        else:
            _orca.refuse_unsendable(args.prompt)
            out = code(os.path.abspath(args.worktree), args.title, args.planner, args.prompt, args.command)
    except (_orca.OrcaError, OSError, RuntimeError, ValueError) as exc:
        print(f"wlaunch: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
