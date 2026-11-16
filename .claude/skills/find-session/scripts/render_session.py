#!/usr/bin/env python3
"""Render Claude Code session transcripts as readable text.

A raw session jsonl is mostly tool output and metadata, and a long orchestrator session can
pass 100 MB. A reader needs the conversation: user turns, assistant text, tool calls, results
(truncated) and tool errors (kept longer). Two modes:

- `--session <id-prefix>`: render one session, searched across every project dir.
- `--repo <path>`: render the newest `--count` sessions of a repo AND its sibling worktrees
  (project dirs `<slug>`, `<slug>-wt-*`, ...), because worker and reviewer sessions run in
  worktrees. It skips `--exclude` ids (pass the current session) and sub-agent sidechains.

Each session becomes one .txt in `--out`. A session longer than `--chunk-bytes` is split into
parts so that a sub-agent can read each part whole. A manifest lists session id, role guess
(main checkout / worker / reviewer, from the worktree dir name), sizes and files.

Python only, no shell pipelines: hooks that rewrite shell commands can truncate piped output.

Usage:
  render_session.py --session 2dcf6838 --out /tmp/x
  render_session.py --repo ~/projects/app --out /tmp/retro --count 5 --exclude <current-id> \\
      [--since 2026-11-01] [--chunk-bytes 750000] [--config-dir ~/.claude-work]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def trunc(value, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else f"{text[:limit]}…[+{len(text) - limit}]"


def condense(src: Path) -> list[str]:
    lines: list[str] = []
    with src.open(errors="replace") as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if entry.get("isSidechain"):
                continue
            ts = (entry.get("timestamp") or "")[:19].replace("T", " ")
            kind = entry.get("type")
            content = (entry.get("message") or {}).get("content")
            if kind == "user":
                if isinstance(content, str):
                    lines.append(f"[{ts}] USER: {trunc(content, 3000)}")
                    continue
                for block in content or []:
                    if block.get("type") == "text":
                        lines.append(f"[{ts}] USER: {trunc(block['text'], 3000)}")
                    elif block.get("type") == "tool_result":
                        body = block.get("content")
                        if isinstance(body, list):
                            body = " ".join(part.get("text", "") for part in body if isinstance(part, dict))
                        is_err = bool(block.get("is_error"))
                        tag = "TOOL_ERR" if is_err else "RESULT"
                        lines.append(f"[{ts}]   {tag}: {trunc(body or '', 1200 if is_err else 400)}")
            elif kind == "assistant" and isinstance(content, list):
                for block in content:
                    if block.get("type") == "text" and block["text"].strip():
                        lines.append(f"[{ts}] ASSISTANT: {trunc(block['text'], 2500)}")
                    elif block.get("type") == "tool_use":
                        lines.append(f"[{ts}]   CALL {block['name']}: {trunc(block.get('input'), 600)}")
            elif kind == "system" and entry.get("content"):
                lines.append(f"[{ts}] SYSTEM: {trunc(entry['content'], 500)}")
    return lines


def split(lines: list[str], limit: int) -> list[list[str]]:
    parts: list[list[str]] = [[]]
    size = 0
    for line in lines:
        if size + len(line) > limit and parts[-1]:
            parts.append([])
            size = 0
        parts[-1].append(line)
        size += len(line) + 1
    return parts


def role_guess(project_dir: str, base_slug: str) -> str:
    if not base_slug:
        return "-"
    suffix = project_dir[len(base_slug) :]
    if suffix.startswith("-wt-rev"):
        return "reviewer"
    if suffix.startswith("-wt-"):
        return "worker"
    return "main checkout"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--session", help="render one session (id or id prefix), any project")
    mode.add_argument("--repo", help="render the newest sessions of this repo and its worktrees")
    ap.add_argument("--out", required=True, help="output dir (use the session scratchpad)")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--since", help="only sessions modified on/after YYYY-MM-DD")
    ap.add_argument("--exclude", action="append", default=[], help="session id to skip (repeatable)")
    ap.add_argument("--chunk-bytes", type=int, default=750_000)
    ap.add_argument(
        "--config-dir",
        default=os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")),
        help="Claude config dir holding projects/ (default: $CLAUDE_CONFIG_DIR or ~/.claude)",
    )
    args = ap.parse_args()

    projects = Path(args.config_dir) / "projects"
    if not projects.is_dir():
        print(f"no projects dir at {projects}", file=sys.stderr)
        return 1

    since = None
    if args.since:
        from datetime import datetime

        since = datetime.fromisoformat(args.since).timestamp()

    candidates = []
    if args.session:
        base_slug = ""
        candidates = [(f.stat().st_mtime, f) for f in projects.glob(f"*/{args.session}*.jsonl")]
    else:
        base_slug = str(Path(args.repo).expanduser().resolve()).replace("/", "-").replace(".", "-")
        for pdir in projects.iterdir():
            if not pdir.is_dir() or not pdir.name.startswith(base_slug):
                continue
            for f in pdir.glob("*.jsonl"):
                mtime = f.stat().st_mtime
                if f.stem in args.exclude or (since and mtime < since):
                    continue
                candidates.append((mtime, f))
    candidates.sort(reverse=True)
    picked = candidates[: args.count]
    if not picked:
        print("no sessions matched", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"{'session':10} {'role':13} {'raw MB':>7} {'cond KB':>8}  files  (project dir)")
    for _, f in picked:
        lines = condense(f)
        label = f.parent.name[len(base_slug) :].lstrip("-") if base_slug else ""
        tag = f"{label or 'main'}_{f.stem[:8]}" if base_slug else f.stem[:8]
        parts = split(lines, args.chunk_bytes)
        names = []
        for i, part in enumerate(parts):
            name = f"{tag}.txt" if len(parts) == 1 else f"{tag}.part{i}.txt"
            (out / name).write_text("\n".join(part))
            names.append(name)
        cond_kb = sum(len(line) + 1 for line in lines) // 1024
        raw_mb = f.stat().st_size / 1_048_576
        print(
            f"{f.stem[:8]:10} {role_guess(f.parent.name, base_slug):13} {raw_mb:7.1f} {cond_kb:8}  "
            f"{', '.join(names)}  ({f.parent.name})"
        )
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
