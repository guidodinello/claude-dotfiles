"""Shared helpers for wstat.py, wwatch2.py and wplan.py: find a Claude Code session's
transcript from its working directory and read the worker's state out of it.

Claude Code stores a session's transcripts in
  ${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<cwd with every non-alphanumeric char as "-">/
and, when that name exceeds 200 chars, keeps the first 200 plus "-<hash>".
"""
import glob
import json
import os
import re

MAX_NAME = 200
ORCA_WORKSPACES = os.environ.get("ORCA_WORKSPACES", os.path.expanduser("~/orca/workspaces"))


def projects_dir():
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.path.join(config, "projects")


def sanitize(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def first_cwd(project):
    for f in glob.glob(os.path.join(project, "*.jsonl")):
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        cwd = json.loads(line).get("cwd")
                    except (ValueError, AttributeError):
                        continue
                    if cwd:
                        return cwd
        except OSError:
            continue
    return None


def _for_path(path):
    base = projects_dir()
    name = sanitize(path)
    if len(name) <= MAX_NAME:
        return os.path.join(base, name)
    matches = glob.glob(os.path.join(base, glob.escape(name[:MAX_NAME]) + "-*"))
    for m in matches:
        if first_cwd(m) == path:
            return m
    return matches[0] if len(matches) == 1 else None


def resolve(arg):
    """Transcript dir for a worktree path, a transcript dir name, or a name relative to
    $ORCA_WORKSPACES (the old "<repo>-<worktree>" argument). May not exist yet."""
    base = projects_dir()
    looks_like_path = os.sep in arg or arg.startswith("~") or os.path.isdir(arg)
    if looks_like_path:
        path = os.path.abspath(os.path.expanduser(arg))
        candidates = [path, os.path.realpath(path)]
        for p in candidates:
            d = _for_path(p)
            if d and os.path.isdir(d):
                return d
        return _for_path(path) or os.path.join(base, sanitize(path))
    if os.path.isdir(os.path.join(base, arg)):
        return os.path.join(base, arg)
    return os.path.join(base, sanitize(ORCA_WORKSPACES) + "-" + arg)


def latest(project):
    """Newest main-session transcript in a project dir, or None before the first write."""
    files = glob.glob(os.path.join(project, "*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def rows(transcript):
    out = []
    with open(transcript, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def state(transcript):
    """(pending tool_use block or None, last assistant text, row count)."""
    rs = rows(transcript)
    answered = set()
    for r in rs:
        content = (r.get("message") or {}).get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    answered.add(b.get("tool_use_id"))
    pending, last_text = None, ""
    for r in rs:
        m = r.get("message") or {}
        if m.get("role") != "assistant":
            continue
        for b in m.get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text" and b.get("text", "").strip():
                last_text = b["text"]
            if b.get("type") == "tool_use" and b.get("id") not in answered:
                pending = b
    return pending, last_text, len(rs)


def latest_plan(transcript):
    plan = None
    for r in rows(transcript):
        m = r.get("message") or {}
        if m.get("role") != "assistant":
            continue
        for b in m.get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "ExitPlanMode":
                plan = (b.get("input") or {}).get("plan")
    return plan


def subagent_mtime(transcript):
    subs = glob.glob(os.path.join(transcript[: -len(".jsonl")], "subagents", "*.jsonl"))
    return max((os.path.getmtime(x) for x in subs), default=0)
