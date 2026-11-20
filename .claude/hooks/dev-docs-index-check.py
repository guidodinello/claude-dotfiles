#!/usr/bin/env python3
"""Stop hook: before Claude ends a turn, check the my-dev-things/ indexes it may have touched.

Runs the dev-docs-index skill's check_index.py when the session's cwd has a my-dev-things/
folder and a doc or script in it (check_index.NAV_SUFFIXES) changed since the session
started (the transcript's creation time). Logs and data a running stack keeps rewriting do
not count. Only findings about this session's work are reported: a gap in a folder where it
changed a file, or a missing README or unnamed subfolder on the path down to one. An old
gap in another folder, or a parent's, never blocks this session. Another session's half-written
folder still can, when this session changed a doc in that folder's parent.
On findings, exit 2: Claude Code keeps the turn going and shows stderr to Claude, which
fixes the indexes before it stops. Otherwise exit 0.

Not covered: a deleted or moved file (nothing new to see), and worktree sessions, whose
cwd has the `.my-dev-things` link rather than `my-dev-things/`.

This is a convenience check, not a policy control, so it fails open: bad input, a missing
checker or any error exits 0 and never keeps Claude from stopping. `stop_hook_active`
(already continuing because of a Stop hook) also exits 0, so it blocks at most once per
turn and can never loop.
"""

import json
import os
import sys
import time
from pathlib import Path

SKIPPED_DIRS = {"node_modules", "__pycache__", ".git", ".venv"}
CHECKER = Path(__file__).parent.parent / "skills" / "dev-docs-index" / "scripts"


def session_start(transcript: str | None) -> float:
    try:
        st = os.stat(transcript or "")
    except OSError:
        return time.time() - 3600
    return getattr(st, "st_birthtime", st.st_ctime)


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
    """A finding about this session's work: a gap in a folder it changed a file in, or a
    missing README / unnamed subfolder on the path down to one."""
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
    root = Path(data.get("cwd") or os.getcwd()) / "my-dev-things"
    if not root.is_dir():
        return 0
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(CHECKER))
    try:
        import check_index  # ty: ignore[unresolved-import]

        own, chain = changed_paths(root, session_start(data.get("transcript_path")),
                                   check_index.NAV_SUFFIXES)
        if not own:
            return 0
        findings = [f for f in check_index.check_tree(root) if relevant(f, own, chain)]
    except Exception:
        return 0
    if not findings:
        return 0
    print(
        "Docs you changed in my-dev-things/ this session left index gaps (dev-docs-index "
        "skill). Add each item to its README.md, or to a .index-ignore if it is per-run "
        "scaffolding, then stop:\n" + "\n".join(findings),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
