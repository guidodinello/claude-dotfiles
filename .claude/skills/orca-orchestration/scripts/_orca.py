"""Shared helpers for wlaunch.py and wsend.py: call the `orca` CLI and send one line to a
terminal the way Claude Code's prompt needs it.

The binary is `$ORCA_BIN` (default `orca`) so tests can point it at a fake.
"""
import json
import os
import subprocess
import time

MAX_LINE = 400
SETTLE_SECS = float(os.environ.get("WSEND_SETTLE_SECS", 1))


class OrcaError(Exception):
    """An orca call failed, or answered with something that is not the expected JSON."""


def orca(*args):
    """Run `orca <args> --json` and return its `result` object. Raises OrcaError on failure."""
    cmd = [os.environ.get("ORCA_BIN", "orca"), *args, "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    label = " ".join(args[:2])
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        detail = (proc.stderr or proc.stdout).strip()
        raise OrcaError(f"orca {label}: exit {proc.returncode}, no JSON: {detail}") from None
    if proc.returncode != 0 or not data.get("ok"):
        raise OrcaError(f"orca {label}: {data.get('error') or proc.stderr.strip() or data}")
    return data.get("result") or {}


def refuse_unsendable(text):
    """Raise ValueError for text that must go through .orchestrator-answers.md instead."""
    if "\n" in text or "\r" in text or len(text) > MAX_LINE:
        raise ValueError(
            f"one line of at most {MAX_LINE} chars only: orca terminal send truncates long "
            "text. Write it to <worktree>/.orchestrator-answers.md and send a pointer to it"
        )


def send_line(handle, text):
    """Type `text` without Enter, let the prompt settle, then press a bare Enter."""
    refuse_unsendable(text)
    orca("terminal", "send", "--terminal", handle, "--text", text)
    time.sleep(SETTLE_SECS)
    orca("terminal", "send", "--terminal", handle, "--text", "", "--enter")


def send_menu_choice(handle, number):
    """A menu takes the bare option number, no Enter."""
    orca("terminal", "send", "--terminal", handle, "--text", str(number))
