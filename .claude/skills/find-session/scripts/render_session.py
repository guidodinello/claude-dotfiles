#!/usr/bin/env python3
"""Render Claude Code session transcripts as readable text.

A raw session jsonl is mostly tool output and metadata, and a long orchestrator session can
pass 100 MB. A reader needs the conversation: user turns, assistant text, tool calls, results
(truncated) and tool errors (kept longer). Two modes:

- `--session <id-prefix | path.jsonl>`: render one session. An id prefix is searched across
  every project dir; a path to a .jsonl (including a sub-agent file under `<session>/subagents/`)
  is used as is.
- `--repo <path>`: render the newest `--count` sessions of a repo AND its sibling worktrees
  (project dirs `<slug>`, `<slug>-wt-*`, ...), because worker and reviewer sessions run in
  worktrees. It skips `--exclude` ids (pass the current session) and sub-agent sidechains.

Each session becomes one .txt in `--out`. A session longer than `--chunk-bytes` is split into
parts so that a sub-agent can read each part whole. A manifest lists session id, role guess
(main checkout / worker / reviewer, from the worktree dir name), sizes and files. The jsonl is
streamed and parts are written as they fill, so memory stays bounded for any session size.

Filters (all times are UTC, the same zone as the `[timestamp]` printed on every line; a value
without a timezone is read as UTC, and a date-only `--until` covers that whole day):
- `--errors-only`: only tool-error lines, each naming the tool and kept on one line (newlines shown as ⏎).
- `--since` / `--until`: only records inside the window. Records without a timestamp are
  dropped while a window is active. In `--repo` mode `--since` also skips files not modified
  since then.
- `--max-chars N`: truncate every kind of line at N chars (defaults differ per kind).

Python only, no shell pipelines: hooks that rewrite shell commands can truncate piped output.

Usage:
  render_session.py --session 2dcf6838 --out /tmp/x [--errors-only]
  render_session.py --session ~/.claude/projects/<dir>/<id>.jsonl --out /tmp/x --since 2026-11-01T09:00
  render_session.py --repo ~/projects/app --out /tmp/retro --count 5 --exclude <current-id> \\
      [--since 2026-11-01] [--chunk-bytes 750000] [--config-dir ~/.claude-work]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

LIMITS = {"user": 3000, "assistant": 2500, "call": 600, "result": 400, "error": 1200, "system": 500}
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"


def projects_dirs(config_dir: str | None) -> list[Path]:
    """--config-dir, else $CLAUDE_CONFIG_DIR, else every default dir that exists."""
    explicit = config_dir or os.environ.get("CLAUDE_CONFIG_DIR")
    if explicit:
        projects = Path(explicit).expanduser() / "projects"
        if not projects.is_dir():
            sys.exit(f"no projects dir at {projects}")
        return [projects]
    found: dict[Path, Path] = {}
    for name in (".claude", ".claude-work"):
        candidate = Path.home() / name / "projects"
        if candidate.is_dir():
            found.setdefault(candidate.resolve(), candidate)
    return list(found.values())


def parse_bound(text: str, *, end_of_day: bool) -> datetime:
    """YYYY-MM-DD or ISO datetime to an aware UTC datetime; naive input means UTC."""
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if len(text) == 10 and end_of_day:
        value = value.replace(hour=23, minute=59, second=59)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def trunc(value, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else f"{text[:limit]}…[+{len(text) - limit}]"


def condense(
    src: Path,
    *,
    errors_only: bool = False,
    since: str | None = None,
    until: str | None = None,
    max_chars: int | None = None,
) -> Iterator[str]:
    """Yield one rendered line per record of interest, streaming the jsonl."""
    limits = {k: max_chars for k in LIMITS} if max_chars else LIMITS
    keep_sidechain = "subagents" in src.parts  # a sub-agent file is all sidechain records
    tool_names: dict[str, str] = {}
    with src.open(errors="replace") as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict):
                continue
            if entry.get("isSidechain") and not keep_sidechain:
                continue
            if entry.get("type") == "assistant" and isinstance(entry.get("message", {}).get("content"), list):
                # register tool names before the time filter, so an error inside the window
                # still names a tool whose call came before it
                for block in entry["message"]["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_names[block.get("id", "")] = block.get("name", "?")
            stamp = entry.get("timestamp") or ""
            if (since or until) and (not stamp or (since and stamp[:19] < since) or (until and stamp[:19] > until)):
                continue
            ts = stamp[:19].replace("T", " ")
            kind = entry.get("type")
            content = (entry.get("message") or {}).get("content")
            if kind == "user":
                label = "COMPACT SUMMARY" if entry.get("isCompactSummary") else "USER"
                if isinstance(content, str):
                    if not errors_only:
                        yield f"[{ts}] {label}: {trunc(content, limits['user'])}"
                    continue
                for block in content or []:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text" and not errors_only:
                        yield f"[{ts}] {label}: {trunc(block.get('text', ''), limits['user'])}"
                    elif block.get("type") == "tool_result":
                        is_err = bool(block.get("is_error"))
                        if errors_only and not is_err:
                            continue
                        body = block.get("content")
                        if isinstance(body, list):
                            body = " ".join(part.get("text", "") for part in body if isinstance(part, dict))
                        if is_err:
                            name = tool_names.get(block.get("tool_use_id", ""), "?")
                            one_line = " ⏎ ".join(trunc(body or "", limits["error"]).splitlines())
                            yield f"[{ts}]   TOOL_ERR ({name}): {one_line}"
                        else:
                            yield f"[{ts}]   RESULT: {trunc(body or '', limits['result'])}"
            elif kind == "assistant" and isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use":
                        if not errors_only:
                            yield f"[{ts}]   CALL {block.get('name')}: {trunc(block.get('input'), limits['call'])}"
                    elif block.get("type") == "text" and block.get("text", "").strip() and not errors_only:
                        yield f"[{ts}] ASSISTANT: {trunc(block['text'], limits['assistant'])}"
            elif kind == "system" and entry.get("content") and not errors_only:
                yield f"[{ts}] SYSTEM: {trunc(entry['content'], limits['system'])}"


def write_parts(lines: Iterator[str], out: Path, tag: str, limit: int) -> tuple[list[str], int, int]:
    """Write lines to .partN.txt files as they arrive; a single part is renamed to <tag>.txt."""
    names: list[str] = []
    count = size = total = 0
    fh = None
    for line in lines:
        if fh is None or (size + len(line) > limit and size):
            if fh:
                fh.close()
            names.append(f"{tag}.part{len(names)}.txt")
            fh = (out / names[-1]).open("w")
            size = 0
        fh.write(line + "\n")
        size += len(line) + 1
        total += len(line) + 1
        count += 1
    if fh:
        fh.close()
    if len(names) <= 1:
        final = f"{tag}.txt"
        if names:
            (out / names[0]).rename(out / final)
        else:
            (out / final).write_text("")
        names = [final]
    return names, count, total


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
    mode.add_argument("--session", help="render one session: id or id prefix (any project), or a .jsonl path")
    mode.add_argument("--repo", help="render the newest sessions of this repo and its worktrees")
    ap.add_argument("--out", required=True, help="output dir (use the session scratchpad)")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--since", help="only records at/after this UTC time (YYYY-MM-DD or ISO datetime)")
    ap.add_argument("--until", help="only records at/before this UTC time (a date covers that whole day)")
    ap.add_argument("--errors-only", action="store_true", help="only tool-error lines")
    ap.add_argument("--max-chars", type=int, help="truncate every line kind at N chars")
    ap.add_argument("--exclude", action="append", default=[], help="session id to skip (repeatable)")
    ap.add_argument("--chunk-bytes", type=int, default=750_000)
    ap.add_argument(
        "--config-dir",
        help="Claude config dir holding projects/ (default: $CLAUDE_CONFIG_DIR, else ~/.claude and ~/.claude-work)",
    )
    args = ap.parse_args()

    since_dt = parse_bound(args.since, end_of_day=False) if args.since else None
    until_dt = parse_bound(args.until, end_of_day=True) if args.until else None
    since = since_dt.strftime(TS_FORMAT) if since_dt else None
    until = until_dt.strftime(TS_FORMAT) if until_dt else None

    candidates: list[tuple[float, Path]] = []
    base_slug = ""
    if args.session and Path(args.session).expanduser().is_file():
        path = Path(args.session).expanduser()
        candidates = [(path.stat().st_mtime, path)]
    else:
        dirs = projects_dirs(args.config_dir)
        if not dirs:
            print("no projects dir found (try --config-dir)", file=sys.stderr)
            return 1
        if args.session:
            candidates = [(f.stat().st_mtime, f) for d in dirs for f in d.glob(f"*/{args.session}*.jsonl")]
        else:
            base_slug = str(Path(args.repo).expanduser().resolve()).replace("/", "-").replace(".", "-")
            for d in dirs:
                for pdir in d.iterdir():
                    if not pdir.is_dir() or not pdir.name.startswith(base_slug):
                        continue
                    for f in pdir.glob("*.jsonl"):
                        mtime = f.stat().st_mtime
                        if f.stem in args.exclude or (since_dt and mtime < since_dt.timestamp()):
                            continue
                        candidates.append((mtime, f))
    candidates.sort(reverse=True)
    picked = candidates[: args.count]
    if not picked:
        print("no sessions matched", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print("times are UTC")
    print(f"{'session':10} {'role':13} {'raw MB':>7} {'lines':>7} {'cond KB':>8}  files  (project dir)")
    for _, f in picked:
        label = f.parent.name[len(base_slug) :].lstrip("-") if base_slug else ""
        tag = f"{label or 'main'}_{f.stem[:8]}" if base_slug else f.stem[:8]
        lines = condense(f, errors_only=args.errors_only, since=since, until=until, max_chars=args.max_chars)
        names, count, total = write_parts(lines, out, tag, args.chunk_bytes)
        raw_mb = f.stat().st_size / 1_048_576
        print(
            f"{f.stem[:8]:10} {role_guess(f.parent.name, base_slug):13} {raw_mb:7.1f} {count:7} {total // 1024:8}  "
            f"{', '.join(names)}  ({f.parent.name})"
        )
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
