#!/usr/bin/env python3
"""Tear down a git worktree: close its herdr workspace, remove it, delete its merged branch.

usage: teardown.py WORKTREE [--label LABEL] [--force] [--dry-run]

Run it from the main checkout or the orchestrator, never from inside the worktree or
from the herdr workspace being closed. Run with `python3 -I`.

herdr: `herdr workspace close` takes a workspace ID, not a label. Closing by label fails
silently. This script resolves the id from `herdr workspace list` (label -> workspace_id),
closes it, then lists again and fails if the id is still there.

Every check runs before any action. Refused (exit 2) when:
  - WORKTREE is the main checkout, or is not a worktree of this repo
  - the cwd is inside WORKTREE
  - WORKTREE has uncommitted changes and --force is not set. Untracked symlinks named
    node_modules or .venv (the links in-worktree creates) do not count; any other
    untracked symlink does
  - WORKTREE is a detached HEAD whose commit is on no branch (removing it would lose the
    commits) and --force is not set
  - --label matches two or more workspaces, or none (none is allowed with --force)
  - the resolved workspace is the one running this script ($HERDR_WORKSPACE_ID), or
    HERDR_ENV=1 but HERDR_WORKSPACE_ID is unset (fail closed)

Actions, in order:
  1. herdr workspace close <id>   (verified by listing again)
  2. unlink the node_modules/.venv symlinks (symlinks only, never a real directory, so the
     main checkout's node_modules/.venv stay intact)
  3. git worktree remove --force WORKTREE, git worktree prune
  4. git branch -D BRANCH, only when a MERGED PR exists for it whose head commit equals
     the local branch tip. -D is needed because squash merges make `branch -d` refuse.
     A detached HEAD has no branch. Remote branches are never deleted.

--force skips the uncommitted-changes check, the unreachable-detached-HEAD check and the
"no workspace with that label" refusal. It does not skip the other refusals.

Exit codes: 0 done, 2 refused, 3 tool missing, 1 any other failure.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_REFUSED = 2
EXIT_MISSING_TOOL = 3


class TeardownError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def log(text: str) -> None:
    print(text, flush=True)


# --- pure decision logic -------------------------------------------------------------


def parse_worktree_list(porcelain: str) -> list[dict[str, Any]]:
    """`git worktree list --porcelain` -> [{path, head, branch|None}]; the first entry is the main checkout."""
    entries: list[dict[str, Any]] = []
    for block in porcelain.strip().split("\n\n"):
        entry: dict[str, Any] = {"path": None, "head": None, "branch": None}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            if key == "worktree":
                entry["path"] = value
            elif key == "HEAD":
                entry["head"] = value
            elif key == "branch":
                entry["branch"] = value.removeprefix("refs/heads/")
        if entry["path"]:
            entries.append(entry)
    return entries


def parse_status(porcelain: str) -> list[tuple[str, str]]:
    """`git status --porcelain` -> [(XY, path)]."""
    return [(line[:2], line[3:].rstrip("/")) for line in porcelain.splitlines() if len(line) > 3]


DEP_LINK_NAMES = frozenset({"node_modules", ".venv"})


def is_dep_symlink(rel: str) -> bool:
    """Only the dependency links in-worktree creates; any other untracked symlink is real work."""
    return Path(rel).name in DEP_LINK_NAMES


def is_inside(path: str, parent: str) -> bool:
    p, q = Path(path).resolve(), Path(parent).resolve()
    return p == q or q in p.parents


def match_workspaces(workspaces: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    return [w for w in workspaces if w.get("label") == label]


def branch_decision(branch: str | None, tip: str | None, merged_prs: list[dict[str, Any]]) -> tuple[bool, str]:
    """(delete, reason). Delete only when a merged PR's head commit is the local tip."""
    if not branch:
        return False, "detached HEAD, no branch"
    if not merged_prs:
        return False, f"no merged PR for {branch}"
    if not any(pr.get("headRefOid") == tip for pr in merged_prs):
        return False, f"{branch} has commits the merged PR does not contain"
    return True, f"PR #{merged_prs[0].get('number')} merged"


def plan(
    *,
    target: str,
    worktrees: list[dict[str, Any]],
    cwd: str,
    dirty: list[str],
    dep_symlinks: list[str],
    label: str | None,
    workspaces: list[dict[str, Any]],
    self_workspace_id: str | None,
    force: bool,
    merged_prs: list[dict[str, Any]],
    in_herdr: bool = False,
    head_reachable: bool = True,
) -> list[tuple[str, ...]]:
    """Return the ordered actions, or raise TeardownError(code=EXIT_REFUSED). No I/O."""
    paths = [str(Path(w["path"]).resolve()) for w in worktrees]
    resolved = str(Path(target).resolve())
    if resolved == paths[0]:
        raise TeardownError("refusing to remove the main checkout", EXIT_REFUSED)
    if resolved not in paths:
        raise TeardownError(f"{target} is not a worktree of this repo", EXIT_REFUSED)
    if is_inside(cwd, resolved):
        raise TeardownError("the cwd is inside the worktree; run from the main checkout", EXIT_REFUSED)
    if dirty and not force:
        raise TeardownError(f"worktree has uncommitted changes (use --force): {', '.join(dirty[:5])}", EXIT_REFUSED)
    entry = worktrees[paths.index(resolved)]
    if entry["branch"] is None and not head_reachable and not force:
        raise TeardownError("detached HEAD is on no branch; removing it would lose commits (use --force)", EXIT_REFUSED)

    actions: list[tuple[str, ...]] = []
    if label is not None:
        if in_herdr and not self_workspace_id:
            raise TeardownError(
                "HERDR_ENV=1 but HERDR_WORKSPACE_ID is unset; cannot rule out closing our own workspace", EXIT_REFUSED
            )
        found = match_workspaces(workspaces, label)
        if len(found) > 1:
            raise TeardownError(f"label {label!r} matches {len(found)} herdr workspaces", EXIT_REFUSED)
        if not found and not force:
            raise TeardownError(f"no herdr workspace labelled {label!r} (use --force to continue)", EXIT_REFUSED)
        if found:
            workspace_id = found[0]["workspace_id"]
            if workspace_id == self_workspace_id:
                raise TeardownError("that workspace is the one running this script", EXIT_REFUSED)
            actions.append(("close_workspace", workspace_id))
    actions += [("unlink", p) for p in dep_symlinks]
    actions += [("remove_worktree", resolved), ("prune",)]

    delete, reason = branch_decision(entry["branch"], entry["head"], merged_prs)
    actions.append(("delete_branch", entry["branch"], reason) if delete else ("keep_branch", reason))
    return actions


# --- I/O -----------------------------------------------------------------------------


def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> str:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise TeardownError(f"{cmd[0]} is not installed", EXIT_MISSING_TOOL) from exc
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()  # herdr reports errors as JSON on stdout
        raise TeardownError(f"{' '.join(cmd[:3])} failed ({proc.returncode}): {detail}")
    return proc.stdout


def list_workspaces() -> list[dict[str, Any]]:
    out = run(["herdr", "workspace", "list"])
    try:
        return json.loads(out)["result"]["workspaces"]
    except (ValueError, KeyError, TypeError) as exc:
        raise TeardownError(f"unexpected `herdr workspace list` output: {out[:200]}") from exc


def gather(args: argparse.Namespace) -> dict[str, Any]:
    target = str(Path(args.worktree).resolve())
    worktrees = parse_worktree_list(run(["git", "worktree", "list", "--porcelain"]))
    dirty: list[str] = []
    dep_symlinks: list[str] = []
    merged: list[dict[str, Any]] = []
    head_reachable = True
    entry = next((w for w in worktrees if str(Path(w["path"]).resolve()) == target), None)
    if entry and str(Path(worktrees[0]["path"]).resolve()) != target:
        for code, rel in parse_status(run(["git", "status", "--porcelain"], cwd=target)):
            full = os.path.join(target, rel)
            if code == "??" and os.path.islink(full) and is_dep_symlink(rel):
                dep_symlinks.append(full)
            else:
                dirty.append(rel)
        if entry["branch"]:
            out = run(
                ["gh", "pr", "list", "--head", entry["branch"], "--state", "merged", "--json", "number,headRefOid"],
                cwd=target,
            )
            try:
                merged = json.loads(out or "[]")
            except ValueError as exc:
                raise TeardownError(f"unexpected `gh pr list` output: {out[:200]}") from exc
        elif entry["head"]:
            head_reachable = bool(run(["git", "branch", "-a", "--contains", entry["head"]], cwd=target).strip())
    workspaces = list_workspaces() if args.label else []
    return {
        "target": target,
        "worktrees": worktrees,
        "cwd": os.getcwd(),
        "dirty": dirty,
        "dep_symlinks": dep_symlinks,
        "label": args.label,
        "workspaces": workspaces,
        "self_workspace_id": os.environ.get("HERDR_WORKSPACE_ID"),
        "force": args.force,
        "merged_prs": merged,
        "in_herdr": os.environ.get("HERDR_ENV") == "1",
        "head_reachable": head_reachable,
    }


def execute(actions: list[tuple[str, ...]], main_dir: str) -> None:
    for action in actions:
        kind = action[0]
        if kind == "close_workspace":
            run(["herdr", "workspace", "close", action[1]])
            if any(w["workspace_id"] == action[1] for w in list_workspaces()):  # close was a silent no-op before
                raise TeardownError(
                    f"herdr workspace {action[1]} is still listed after close; nothing else was changed"
                )
            log(f"closed herdr workspace {action[1]}")
        elif kind == "unlink":
            if os.path.islink(action[1]):  # never a real directory
                os.unlink(action[1])
                log(f"unlinked {action[1]}")
        elif kind == "remove_worktree":
            run(["git", "worktree", "remove", "--force", action[1]], cwd=main_dir)
            log(f"removed worktree {action[1]}")
        elif kind == "prune":
            run(["git", "worktree", "prune"], cwd=main_dir)
        elif kind == "delete_branch":
            run(["git", "branch", "-D", action[1]], cwd=main_dir)
            log(f"deleted branch {action[1]} ({action[2]})")
        elif kind == "keep_branch":
            log(f"kept branch: {action[1]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worktree")
    ap.add_argument("--label", help="herdr workspace label to close (resolved to its id)")
    ap.add_argument("--force", action="store_true", help="allow uncommitted changes and a missing workspace")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    args = ap.parse_args(argv)
    try:
        for tool in ("git", "gh") + (("herdr",) if args.label else ()):
            if shutil.which(tool) is None:
                raise TeardownError(f"{tool} is not installed", EXIT_MISSING_TOOL)
        inputs = gather(args)
        actions = plan(**inputs)
        for action in actions:
            log(("would " if args.dry_run else "") + " ".join(action))
        if not args.dry_run:
            execute(actions, str(Path(inputs["worktrees"][0]["path"])))
        return 0
    except TeardownError as exc:
        log(f"{'REFUSED' if exc.code == EXIT_REFUSED else 'FATAL'} {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
