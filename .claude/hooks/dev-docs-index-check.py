#!/usr/bin/env python3
"""Stop hook: before Claude ends a turn, check the my-dev-things/ indexes it may have touched.

Runs the dev-docs-index skill's check_index.py when the session's cwd has a my-dev-things/
folder and a doc or script in it (check_index.NAV_SUFFIXES) changed since the session
started. The start is the first timestamped transcript entry, not file metadata: Linux has
no creation time, and the transcript's ctime moves with every message. Logs and data a
running stack keeps rewriting do not count.

Findings are kept when they are about a folder that changed: a gap in a folder where a
doc or script changed, or a missing README or unnamed subfolder on the path down to one
(without those the new work is unreachable, so they count even when they are old). An old
unnamed file in a parent, or any gap in an unrelated folder, does not block.

"Changed" is mtime against the session start, with no attribution: a doc another session
or a manual edit wrote under my-dev-things/ in the meantime counts too, and its gaps are
reported here. Also not covered: a deleted or moved file (nothing new to see), and worktree
sessions, whose cwd has the `.my-dev-things` link rather than `my-dev-things/`.

On findings, exit 2: Claude Code keeps the turn going and shows stderr to Claude, which
fixes the indexes before it stops. Otherwise exit 0.

This is a convenience check, not a policy control, so it fails open: bad input, an
unreadable transcript, a missing checker or any error exits 0 and never keeps Claude from
stopping. `stop_hook_active` (already continuing because of a Stop hook) also exits 0, so
it blocks at most once per turn and can never loop.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

SKIPPED_DIRS = {"node_modules", "__pycache__", ".git", ".venv"}
CHECKER = Path(__file__).parent.parent / "skills" / "dev-docs-index" / "scripts"
TRANSCRIPT_LINES_SCANNED = 200


def session_start(transcript: str | None) -> float | None:
    """Epoch seconds of the first timestamped transcript entry, or None when unreadable."""
    if not transcript:
        return None
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for _, line in zip(range(TRANSCRIPT_LINES_SCANNED), f):
                try:
                    stamp = json.loads(line).get("timestamp")
                except (ValueError, AttributeError):
                    continue
                if isinstance(stamp, str):
                    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except (OSError, ValueError):
        return None
    return None


def changed_paths(root: Path, since: float, suffixes: set[str]) -> tuple[set[Path], set[Path]]:
    """(folders holding a changed doc or script, those folders plus their ancestors to root)."""
    own: set[Path] = set()
    chain: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix not in suffixes:
                continue
            try:
                if path.stat().st_mtime <= since:
                    continue
            except OSError:
                continue
            own.add(path.parent)
            folder = path.parent
            while folder not in chain:
                chain.add(folder)
                if folder == root:
                    break
                folder = folder.parent
    return own, chain


def relevant(finding: str, own: set[Path], chain: set[Path]) -> bool:
    """A gap in a folder where a file changed, or a missing README / unnamed subfolder on
    the path down to one."""
    where, _, problem = finding.partition(": ")
    path = Path(where)
    if problem == "no README.md":
        return path in chain
    if problem.startswith("does not name subfolder "):
        return path.parent / problem.removeprefix("does not name subfolder ").rstrip("/") in chain
    return path.parent in own


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        return 0
    try:
        root = Path(data.get("cwd") or os.getcwd()) / "my-dev-things"
        if not root.is_dir():
            return 0
        since = session_start(data.get("transcript_path"))
        if since is None:
            return 0
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(CHECKER))
        import check_index  # ty: ignore[unresolved-import]

        own, chain = changed_paths(root, since, check_index.NAV_SUFFIXES)
        if not own:
            return 0
        findings = [f for f in check_index.check_tree(root) if relevant(f, own, chain)]
    except Exception:
        return 0
    if not findings:
        return 0
    print(
        "Index gaps in my-dev-things/ folders that changed this session (dev-docs-index "
        "skill). Name each missing file or subfolder in its README.md (per-run scaffolding "
        "can go in a .index-ignore instead), create each missing README.md, fix each broken "
        "link, then stop:\n" + "\n".join(findings),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
