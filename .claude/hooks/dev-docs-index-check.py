#!/usr/bin/env python3
"""Stop hook: before Claude ends a turn, check the my-dev-things/ indexes it may have touched.

Runs the dev-docs-index skill's check_index.py when the session's cwd has a my-dev-things/
folder and some file in it changed since the session started (the transcript's creation
time). On findings, exit 2: Claude Code keeps the turn going and shows stderr to Claude,
which fixes the indexes before it stops. Otherwise exit 0.

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


def changed_since(root: Path, since: float) -> bool:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
        for name in filenames:
            try:
                if os.stat(os.path.join(dirpath, name)).st_mtime > since:
                    return True
            except OSError:
                continue
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0
    if not isinstance(data, dict) or data.get("stop_hook_active"):
        return 0
    root = Path(data.get("cwd") or os.getcwd()) / "my-dev-things"
    if not root.is_dir() or not changed_since(root, session_start(data.get("transcript_path"))):
        return 0
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(CHECKER))
    try:
        import check_index  # ty: ignore[unresolved-import]

        findings = check_index.check_tree(root)
    except Exception:
        return 0
    if not findings:
        return 0
    print(
        "my-dev-things/ changed this session and its indexes have gaps (dev-docs-index "
        "skill). Add each item to its README.md, or to a .index-ignore if it is per-run "
        "scaffolding, then stop:\n" + "\n".join(findings),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
