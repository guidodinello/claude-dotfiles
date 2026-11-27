#!/usr/bin/env python3
"""Evidence and apply step for the configure-repo skill.

  scan        Count the MCP tools and skills that past sessions in a repo actually used.
  disable-mcp Add MCP servers to the repo's disabledMcpServers in .claude.json, after a backup.

Transcripts live in <config>/projects/<encoded path>/*.jsonl, where the encoded path is the
absolute path with every non-alphanumeric character replaced by '-'. A repo's sessions also
include its worktrees: the paths `git worktree list` reports today, plus any directory that
starts with the encoded repo path followed by '--' (a dot-folder inside the repo, such as
.claude/worktrees/<name>).

Run: python3 repo_config.py scan [--project DIR] [--config-dir DIR] [--json]
     python3 repo_config.py disable-mcp [--project DIR] [--config-dir DIR] NAME [NAME ...]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

COMMAND_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


def config_dir(flag: str | None) -> Path:
    if flag:
        return Path(flag).expanduser()
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env).expanduser() if env else Path.home() / ".claude"


def claude_json(cfg_flag: str | None) -> Path:
    """~/.claude.json by default; <config dir>/.claude.json when a config dir is set."""
    if cfg_flag or os.environ.get("CLAUDE_CONFIG_DIR"):
        return config_dir(cfg_flag) / ".claude.json"
    return Path.home() / ".claude.json"


def encode(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def worktree_paths(project: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project), "worktree", "list", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line[len("worktree "):] for line in out.splitlines() if line.startswith("worktree ")]


def session_dirs(project: Path, cfg: Path) -> list[Path]:
    root = cfg / "projects"
    if not root.is_dir():
        return []
    base = encode(str(project))
    wanted = {base} | {encode(p) for p in worktree_paths(project)}
    return sorted(
        d for d in root.iterdir()
        if d.is_dir() and (d.name in wanted or d.name.startswith(base + "--"))
    )


def mcp_server(tool: str) -> str:
    """mcp__claude_ai_Google_Sheets__get_values -> claude_ai_Google_Sheets (the raw prefix)."""
    return tool.split("__")[1] if tool.count("__") >= 2 else tool


def scan(project: Path, cfg: Path) -> dict:
    dirs = session_dirs(project, cfg)
    mcp: Counter = Counter()
    skills_model: Counter = Counter()
    skills_user: Counter = Counter()
    sessions = 0
    first = last = None
    for d in dirs:
        for f in d.glob("*.jsonl"):
            sessions += 1
            for line in f.open(errors="replace"):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("timestamp")
                if isinstance(ts, str):
                    first = min(first, ts) if first else ts
                    last = max(last, ts) if last else ts
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if rec.get("type") == "user":
                    text = content if isinstance(content, str) else " ".join(
                        c.get("text", "") for c in content or [] if isinstance(c, dict)
                    )
                    skills_user.update(COMMAND_RE.findall(text))
                    continue
                for c in content if isinstance(content, list) else []:
                    if not isinstance(c, dict) or c.get("type") != "tool_use":
                        continue
                    name = c.get("name", "")
                    if name.startswith("mcp__"):
                        mcp[mcp_server(name)] += 1
                    elif name == "Skill":
                        skill = (c.get("input") or {}).get("skill")
                        if skill:
                            skills_model[skill] += 1
    return {
        "project": str(project),
        "session_dirs": [d.name for d in dirs],
        "sessions": sessions,
        "first": first,
        "last": last,
        "mcp_servers": dict(mcp.most_common()),
        "skills_by_model": dict(skills_model.most_common()),
        "commands_by_user": dict(skills_user.most_common()),
    }


def print_scan(r: dict) -> None:
    print(f"project: {r['project']}")
    print(f"sessions: {r['sessions']} in {len(r['session_dirs'])} dir(s), {r['first']} .. {r['last']}")
    dirs = r["session_dirs"]
    shown = [d for d in dirs if "--" not in d]
    for d in shown:
        print(f"  {d}")
    if len(dirs) > len(shown):
        print(f"  + {len(dirs) - len(shown)} worktree dir(s); --json lists them")
    for title, key in (
        ("MCP servers called (raw prefix: calls)", "mcp_servers"),
        ("Skills Claude invoked", "skills_by_model"),
        ("Slash commands the user typed (skills and built-ins)", "commands_by_user"),
    ):
        print(f"\n{title}:")
        for k, v in r[key].items() or [("(none)", "")]:
            print(f"  {k} {v}".rstrip())


def disable_mcp(project: Path, cfg_flag: str | None, names: list[str]) -> int:
    path = claude_json(cfg_flag)
    if not path.is_file():
        sys.exit(f"no {path}; pass --config-dir or set CLAUDE_CONFIG_DIR")
    data = json.loads(path.read_text())
    entry = data.setdefault("projects", {}).setdefault(str(project), {})
    current = entry.get("disabledMcpServers") or []
    merged = current + [n for n in names if n not in current]
    if merged == current:
        print(f"nothing to add; {len(current)} already disabled")
        return 0
    backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup)
    entry["disabledMcpServers"] = merged
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)
    print(f"backup: {backup}")
    print(f"{path}: {len(merged)} disabled for {project} (+{len(merged) - len(current)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("scan", "disable-mcp"):
        p = sub.add_parser(name)
        p.add_argument("--project", default=".", help="repo path (default: cwd)")
        p.add_argument("--config-dir", help="default: $CLAUDE_CONFIG_DIR or ~/.claude")
        if name == "scan":
            p.add_argument("--json", action="store_true")
        else:
            p.add_argument("names", nargs="+", help="server names exactly as `claude mcp list` prints them")
    args = ap.parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    if args.cmd == "disable-mcp":
        return disable_mcp(project, args.config_dir, args.names)
    result = scan(project, config_dir(args.config_dir))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_scan(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
