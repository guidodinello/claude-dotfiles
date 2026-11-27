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
    """~/.claude.json for the default config dir (~/.claude); <config dir>/.claude.json for
    any other. A stale ~/.claude/.claude.json can exist next to the live ~/.claude.json."""
    cfg = config_dir(cfg_flag).resolve()
    if cfg == (Path.home() / ".claude").resolve():
        return Path.home() / ".claude.json"
    return cfg / ".claude.json"


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


def git_common_dir(path: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def recorded_cwd(d: Path) -> str | None:
    """The working directory a transcript dir's sessions ran in, as the transcripts record it."""
    for f in d.glob("*.jsonl"):
        for line in f.open(errors="replace"):
            try:
                cwd = json.loads(line).get("cwd")
            except (json.JSONDecodeError, AttributeError):
                continue
            if isinstance(cwd, str):
                return cwd
    return None


def session_dirs(project: Path, cfg: Path) -> list[tuple[Path, str]]:
    """Transcript dirs for the repo and its worktrees, each tagged with how it matched.

    Live worktrees come from `git worktree list`. A deleted worktree leaves only its
    transcripts, so a dir is also a candidate when its name extends the repo's encoded path
    (`<repo>-wt-301`, `<repo>--claude-worktrees-x`) or names the repo under a `worktrees`
    folder elsewhere (`~/.herdr/worktrees/<repo>-<branch>`). A candidate whose recorded cwd
    still exists is kept only if it shares the repo's git dir; one whose cwd is gone is kept
    and tagged, since nothing else can tell it apart from a sibling repo of a similar name.
    """
    root = cfg / "projects"
    if not root.is_dir():
        return []
    base = encode(str(project))
    live = {encode(p) for p in worktree_paths(project)} - {base}
    name_tag = "-" + encode(project.name) + "-"
    common = git_common_dir(str(project))
    found = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if d.name == base:
            found.append((d, "repo"))
        elif d.name in live:
            found.append((d, "worktree"))
        elif d.name.startswith(base + "-") or ("worktrees" in d.name and name_tag in d.name):
            cwd = recorded_cwd(d)
            if cwd and Path(cwd).exists():
                if common and git_common_dir(cwd) == common:
                    found.append((d, "worktree"))
            else:
                found.append((d, "deleted worktree (matched by name)"))
    return found


def mcp_server(tool: str) -> str:
    """mcp__claude_ai_Google_Sheets__get_values -> claude_ai_Google_Sheets (the raw prefix)."""
    return tool.split("__")[1] if tool.count("__") >= 2 else tool


def scan(project: Path, cfg: Path, skip_session: str | None = None) -> dict:
    """skip_session: a session id to leave out, by default the one running this script
    (Claude Code sets CLAUDE_CODE_SESSION_ID), so /configure-repo doesn't count itself."""
    if skip_session is None:
        skip_session = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    tagged = session_dirs(project, cfg)
    dirs = [d for d, _ in tagged]
    mcp: Counter = Counter()
    skills_model: Counter = Counter()
    skills_user: Counter = Counter()
    sessions = 0
    first = last = None
    for d in dirs:
        for f in d.rglob("*.jsonl"):  # nested: <session>/subagents/*.jsonl
            if skip_session and skip_session in (f.stem, *f.relative_to(d).parts[:-1]):
                continue
            sessions += f.parent == d
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
        "config_dir": str(cfg),
        "session_dirs": {d.name: tag for d, tag in tagged},
        "sessions": sessions,
        "first": first,
        "last": last,
        "mcp_servers": dict(mcp.most_common()),
        "skills_used": dict((skills_model + skills_user).most_common()),
        "skills_by_model": dict(skills_model.most_common()),
        "commands_by_user": dict(skills_user.most_common()),
    }


def print_scan(r: dict) -> None:
    print(f"project: {r['project']}")
    print(f"config dir: {r['config_dir']} (only this account's sessions)")
    if not r["sessions"]:
        print("sessions: 0. No history for this account: decide from the repo (Case 1).")
    else:
        print(f"sessions: {r['sessions']} in {len(r['session_dirs'])} dir(s), {r['first']} .. {r['last']}")
        tags = Counter(r["session_dirs"].values())
        print("  " + ", ".join(f"{n} {t}" for t, n in tags.items()) + "; --json lists them")
    print(f"\nalready disabled here: {len(r['disabled'])} server(s)")
    for k in r["disabled"]:
        print(f"  {k}")
    for title, key in (
        ("MCP servers called (raw prefix: calls)", "mcp_servers"),
        ("Skills and slash commands used (Claude + user; includes built-ins like compact)", "skills_used"),
    ):
        print(f"\n{title}:")
        for k, v in r[key].items() or [("(none)", "")]:
            print(f"  {k} {v}".rstrip())


def connector_prefix(name: str) -> str:
    """`claude.ai monday.com` -> `claude_ai_monday_com`, the prefix its tools carry."""
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def parse_mcp_list(text: str) -> list[str]:
    """claude.ai connector names from `claude mcp list` (lines like `claude.ai X: url - status`)."""
    return [line.split(": ", 1)[0] for line in text.splitlines() if line.startswith("claude.ai ")]


def unused_connectors(listed: list[str], used: dict, keep: list[str]) -> list[str]:
    return [n for n in listed if connector_prefix(n) not in used and n not in keep]


def listed_connectors(project: Path, cfg_flag: str | None) -> list[str]:
    env = dict(os.environ)
    cfg = config_dir(cfg_flag).resolve()
    if cfg == (Path.home() / ".claude").resolve():
        env.pop("CLAUDE_CONFIG_DIR", None)
    else:
        env["CLAUDE_CONFIG_DIR"] = str(cfg)
    out = subprocess.run(["claude", "mcp", "list"], cwd=project, env=env,
                         capture_output=True, text=True, timeout=300).stdout
    names = parse_mcp_list(out)
    if not names:
        sys.exit("`claude mcp list` printed no claude.ai connectors; pass names explicitly")
    return names


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
            p.add_argument("names", nargs="*", help="server names exactly as `claude mcp list` prints them")
            p.add_argument("--all-unused", action="store_true",
                           help="every claude.ai connector `claude mcp list` shows that the scan saw no call to")
            p.add_argument("--keep", action="append", default=[], metavar="NAME",
                           help="with --all-unused: a connector to leave on (repeatable)")
    args = ap.parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    if args.cmd == "disable-mcp":
        names = list(args.names)
        if args.all_unused:
            used = scan(project, config_dir(args.config_dir))["mcp_servers"]
            listed = listed_connectors(project, args.config_dir)
            unused = unused_connectors(listed, used, args.keep)
            kept = [n for n in listed if n not in unused]
            print(f"connectors kept on: {', '.join(kept) or '(none)'}")
            names += [n for n in unused if n not in names]
        if not names:
            sys.exit("no names given; pass names or --all-unused")
        return disable_mcp(project, args.config_dir, names)
    result = scan(project, config_dir(args.config_dir))
    cj = claude_json(args.config_dir)
    data = json.loads(cj.read_text()) if cj.is_file() else {}
    entry = data.get("projects", {}).get(str(project)) or {}
    result["disabled"] = entry.get("disabledMcpServers") or []
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_scan(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
