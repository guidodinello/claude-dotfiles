#!/usr/bin/env python3
"""Spawn the herdr Sonnet reviewer for one PR, wait for its review, reconcile labels.

usage: spawn_reviewer.py PR [-R OWNER/REPO] [--repo-dir DIR] [--config-dir DIR]
                         [--context TEXT] [--timeout MIN] [--keep]
                         [--max-concurrent N]

Reproduces the recipe the orchestrator used to type by hand:

  1. detached worktree of the PR head branch, next to the repo checkout
  2. herdr workspace `rev<PR>` with CLAUDE_CONFIG_DIR set, Claude Sonnet (high
     effort, auto permission mode) started in it
  3. the full `/code-review` brief sent as a prompt
  4. wait for the review to be POSTED (a new review whose body starts with
     "### Code review"), never for the pane to go idle: an idle reviewer can still
     be waiting on its own sub-agents
  5. let the reviewer finish its own label swap (idle is meaningful once the review
     exists), then reconcile the labels from the posted review
  6. close the workspace and remove the worktree (unless --keep)

Labels, decided from the posted review only:
  clean (body says "No issues found", the review has no inline comments, and the
  PR head is still the commit the reviewer's worktree was created from)
      -pending-review +reviewed +ready-to-merge
  anything else, including a head that moved while the review ran (fail closed)
      -pending-review -ready-to-merge +reviewed
  The second form also corrects a reviewer that marked its own findings
  ready-to-merge. Only labels the PR actually carries are removed (gh pr edit fails on
  a label the PR lacks). Nothing is relabelled before the review exists.

Defaults, so the script works from any repo: -R is taken from the repo's origin via
gh, --repo-dir from the cwd's main checkout, --config-dir from $CLAUDE_CONFIG_DIR
(else ~/.claude). At most --max-concurrent (default 3) `rev<N>` workspaces may exist;
a further one is refused.

Run it with run_in_background; it prints one `HH:MM:SS text` line per step.

Exit codes
  0    review posted, labels reconciled
  2    refused: not in herdr, PR not open or a draft, workspace limit, or rev<N> exists
  3    gh, git, herdr or watch.py missing
  124  no review within --timeout; labels untouched, workspace and worktree kept
  1    any other failure, including the PR being merged or closed mid-review (a step's
       stderr is printed); labels untouched, workspace and worktree kept
After 124 or 1 the `rev<N>` workspace is still open and blocks a re-spawn: read it with
`herdr agent read rev<N>`, then `herdr workspace close <id>`. A leftover worktree is
removed automatically by the next run.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

EXIT_REFUSED = 2
EXIT_MISSING_TOOL = 3
EXIT_TIMEOUT = 124

MAX_CONCURRENT = 3
POLL_FLOOR_S = 10.0
REVIEW_HEADER = "### Code review"
WORKSPACE_RE = re.compile(r"^rev\d+$")
CLEAN_MARKER = "No issues found"
WATCH = Path(__file__).resolve().parent / "watch.py"

BRIEF = (
    "Run /code-review on PR {pr} ({repo}). Follow the skill exactly, except for "
    "one override: if the Haiku eligibility check (step 1 or 7) says the PR is "
    "closed or a draft, stop as the skill says, but do not stop because it calls "
    "the PR docs-only, trivial or not needing review; this review was requested, "
    "so run all of steps 1-8. Keep every other part: the CLAUDE.md and summary "
    "agents, the 5 parallel Sonnet reviewers, and per-finding confidence scoring. "
    "No shortcuts and no fallback. If a step fails, retry it once, then stop and "
    "report; do not substitute a single-reviewer pass. "
    "Sub-agents report back as messages, so do not poll "
    "them with sleep. {context}Post the review on the PR as the skill says. Do not "
    "push, merge or edit the branch. This worktree is a detached checkout of the "
    "PR head."
)


class SpawnError(Exception):
    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def log(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {text}", flush=True)


def render_brief(pr: int, repo: str, context: str) -> str:
    return BRIEF.format(pr=pr, repo=repo, context=f"{context.strip()} " if context.strip() else "")


def count_reviewer_workspaces(workspaces: list[dict[str, Any]]) -> int:
    return sum(1 for w in workspaces if WORKSPACE_RE.match(str(w.get("label", ""))))


def check_capacity(workspaces: list[dict[str, Any]], pr: int, limit: int) -> None:
    labels = {str(w.get("label", "")) for w in workspaces}
    if f"rev{pr}" in labels:
        raise SpawnError(f"workspace rev{pr} already exists: a reviewer is already running", EXIT_REFUSED)
    if count_reviewer_workspaces(workspaces) >= limit:
        raise SpawnError(f"{limit} reviewer sessions already running; refusing a {limit + 1}th", EXIT_REFUSED)


def find_new_review(reviews: list[dict[str, Any]], baseline: set[int]) -> dict[str, Any] | None:
    """Newest review not in the baseline whose body is a /code-review summary."""
    fresh = [
        r for r in reviews if r["id"] not in baseline and str(r.get("body") or "").lstrip().startswith(REVIEW_HEADER)
    ]
    return max(fresh, key=lambda r: r["id"]) if fresh else None


def is_clean(review: dict[str, Any], inline_comment_count: int) -> bool:
    return inline_comment_count == 0 and CLEAN_MARKER in str(review.get("body") or "")


def decide_clean(review: dict[str, Any], inline_comments: int, reviewed_sha: str, head_sha: str) -> bool:
    """Clean only if the review says so AND the PR head is still the commit that was reviewed.

    review["commit_id"] is not usable for this: GitHub defaults it to the head at submission.
    """
    return is_clean(review, inline_comments) and bool(reviewed_sha) and reviewed_sha == head_sha


def label_edit_args(clean: bool, present: set[str]) -> list[str]:
    """gh pr edit args; --remove-label fails on a label the PR lacks, so remove only present ones."""
    args: list[str] = []
    drop = ["pending-review"] if clean else ["pending-review", "ready-to-merge"]
    for label in drop:
        if label in present:
            args += ["--remove-label", label]
    args += ["--add-label", "reviewed"]
    if clean:
        args += ["--add-label", "ready-to-merge"]
    return args


def is_start_race(exc: SpawnError) -> bool:
    """herdr rejects an agent start while the new pane is not settled yet.

    agent_pane_busy: the pane's shell is not ready. agent_name_not_found: the name
    "no longer owns the target terminal" right after workspace create.
    """
    text = str(exc)
    return "agent_pane_busy" in text or "agent_name_not_found" in text


def retry_start_race(fn: Any, attempts: int = 8, delay: float = 2.0, sleep: Any = time.sleep) -> Any:
    """Call fn, retrying only the start-race errors (about attempts * delay seconds in all), then fail."""
    for attempt in range(attempts):
        try:
            return fn()
        except SpawnError as exc:
            if not is_start_race(exc) or attempt == attempts - 1:
                raise
            sleep(delay)


def with_retry(fn: Any, attempts: int = 3, delay: float = 5.0, sleep: Any = time.sleep) -> Any:
    """Call fn, retrying SpawnError (a transient gh failure) before giving up."""
    for attempt in range(attempts):
        try:
            return fn()
        except SpawnError as exc:
            if attempt == attempts - 1 or exc.code in (EXIT_REFUSED, EXIT_MISSING_TOOL):
                raise
            sleep(delay)


def run(cmd: list[str], cwd: str | None = None, check: bool = True) -> str:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise SpawnError(f"{cmd[0]} is not installed", EXIT_MISSING_TOOL) from exc
    if check and proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()  # herdr reports errors as JSON on stdout
        raise SpawnError(f"{' '.join(cmd[:3])} failed ({proc.returncode}): {detail}")
    return proc.stdout


def run_json(cmd: list[str], cwd: str | None = None) -> Any:
    out = run(cmd, cwd)
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise SpawnError(f"{cmd[0]} returned invalid JSON: {out[:200]}") from exc


def main_checkout(cwd: str) -> str:
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd).strip()
    return str(Path(common).parent)


def fetch_pr(repo: str, pr: int) -> dict[str, Any]:
    return run_json(["gh", "pr", "view", str(pr), "-R", repo, "--json", "state,isDraft,headRefName,headRefOid,labels"])


def fetch_reviews(repo: str, pr: int) -> list[dict[str, Any]]:
    out = run(["gh", "api", f"repos/{repo}/pulls/{pr}/reviews", "--paginate", "--slurp"])
    pages = json.loads(out or "[]")
    return [r for page in pages for r in page]


def inline_comment_count(repo: str, pr: int, review_id: int) -> int:
    out = run(["gh", "api", f"repos/{repo}/pulls/{pr}/reviews/{review_id}/comments", "--paginate", "--slurp"])
    return sum(len(page) for page in json.loads(out or "[]"))


def wait_for_review(repo: str, pr: int, baseline: set[int], state_file: Path, timeout_s: float) -> dict[str, Any]:
    """Poll the PR until a new /code-review review exists. watch.py is a wake signal only."""
    deadline = time.monotonic() + timeout_s
    while True:
        review = find_new_review(with_retry(lambda: fetch_reviews(repo, pr)), baseline)
        if review:
            return review
        state = with_retry(lambda: fetch_pr(repo, pr))["state"]
        if state != "OPEN":
            raise SpawnError(f"PR {pr} became {state} before a review was posted; rev{pr} kept")
        left = deadline - time.monotonic()
        if left <= 0:
            raise SpawnError(f"no review within the timeout; labels untouched, rev{pr} kept", EXIT_TIMEOUT)
        # exit 124 (watcher timeout) and 0 (an event) both mean "look again"; a fast return
        # (an event that is not a review, or an error) must not turn this into a busy loop.
        started = time.monotonic()
        subprocess.run(
            [
                sys.executable,
                "-I",
                str(WATCH),
                "-R",
                repo,
                "--pr",
                str(pr),
                "--until",
                "review",
                "--exit-on-first-event",
                "--timeout",
                str(max(left / 60, 0.1)),
                "--state",
                str(state_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        time.sleep(max(0.0, POLL_FLOOR_S - (time.monotonic() - started)))


def spawn(args: argparse.Namespace) -> int:
    pr: int = args.pr
    name = f"rev{pr}"
    if os.environ.get("HERDR_ENV") != "1":
        raise SpawnError("not inside a herdr session (HERDR_ENV is not 1)", EXIT_REFUSED)
    for tool in ("gh", "git", "herdr"):
        if shutil.which(tool) is None:
            raise SpawnError(f"{tool} is not installed", EXIT_MISSING_TOOL)
    if not WATCH.exists():
        raise SpawnError(f"watch.py not found next to this script: {WATCH}", EXIT_MISSING_TOOL)

    repo_dir = args.repo_dir or main_checkout(os.getcwd())
    repo = args.repo or run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], repo_dir).strip()
    config_dir = args.config_dir or os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")

    info = fetch_pr(repo, pr)
    if info["state"] != "OPEN":
        raise SpawnError(f"PR {pr} is {info['state']}, not OPEN", EXIT_REFUSED)
    if info.get("isDraft"):
        raise SpawnError(f"PR {pr} is a draft; /code-review skips drafts", EXIT_REFUSED)
    workspaces = run_json(["herdr", "workspace", "list"])["result"]["workspaces"]
    check_capacity(workspaces, pr, args.max_concurrent)

    baseline = {r["id"] for r in fetch_reviews(repo, pr)}
    worktree = Path(repo_dir).parent / f"{Path(repo_dir).name}-wt-{name}"
    state_file = Path(repo_dir).parent / f".{name}-watch.json"
    workspace_id = ""
    keep = args.keep
    try:
        run(["git", "fetch", "-q", "origin"], repo_dir)
        if worktree.exists():  # left by an earlier kept run; no workspace is running (checked above)
            run(["git", "worktree", "remove", "--force", str(worktree)], repo_dir, check=False)
            run(["git", "worktree", "prune"], repo_dir, check=False)
            log(f"removed stale worktree {worktree}")
        run(["git", "worktree", "add", "-q", "--detach", str(worktree), f"origin/{info['headRefName']}"], repo_dir)
        reviewed_sha = run(["git", "rev-parse", "HEAD"], str(worktree)).strip()
        log(f"worktree {worktree} at {reviewed_sha[:7]}")
        created = run_json(
            [
                "herdr",
                "workspace",
                "create",
                "--cwd",
                str(worktree),
                "--label",
                name,
                "--env",
                f"CLAUDE_CONFIG_DIR={config_dir}",
                "--no-focus",
            ]
        )["result"]
        workspace_id = created["workspace"]["workspace_id"]
        pane = created["root_pane"]["pane_id"]
        start_cmd = [
            "herdr",
            "agent",
            "start",
            name,
            "--kind",
            "claude",
            "--pane",
            pane,
            "--",
            "--model",
            "sonnet",
            "--effort",
            "high",
            "--permission-mode",
            "auto",
        ]
        retry_start_race(lambda: run(start_cmd))  # the new pane may not be settled yet
        run(["herdr", "agent", "wait", name, "--until", "idle", "--timeout", "60000"])
        run(["herdr", "agent", "prompt", name, render_brief(pr, repo, args.context)])
        log(f"{name} started, waiting for the review on PR {pr}")

        review = wait_for_review(repo, pr, baseline, state_file, args.timeout * 60)
        log(f"review {review['id']} posted: {review.get('html_url', '')}")
        # The reviewer swaps labels itself right after posting; wait for it to finish
        # before reconciling, or its edit can land after ours. Idle means something now.
        run(["herdr", "agent", "wait", name, "--until", "idle", "--timeout", "300000"], check=False)

        now = with_retry(lambda: fetch_pr(repo, pr))
        comments = with_retry(lambda: inline_comment_count(repo, pr, review["id"]))
        clean = decide_clean(review, comments, reviewed_sha, now["headRefOid"])
        if is_clean(review, comments) and not clean:
            log(f"head moved {reviewed_sha[:7]} -> {now['headRefOid'][:7]} during the review: not ready-to-merge")
        present = {label["name"] for label in now.get("labels") or []}
        run(["gh", "pr", "edit", str(pr), "-R", repo, *label_edit_args(clean, present)])
        log(f"labels set: {'reviewed + ready-to-merge' if clean else 'reviewed'} (clean={clean})")
        return 0
    except BaseException:
        keep = True  # any failure or Ctrl-C: leave the workspace and worktree, the reviewer may be mid-review
        raise
    finally:
        if not keep:
            if workspace_id:
                run(["herdr", "workspace", "close", workspace_id], check=False)
            run(["git", "worktree", "remove", "--force", str(worktree)], repo_dir, check=False)
            state_file.unlink(missing_ok=True)
            log(f"cleaned up {name}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pr", type=int)
    ap.add_argument("-R", "--repo", help="OWNER/REPO (default: origin of --repo-dir, via gh)")
    ap.add_argument("--repo-dir", help="main checkout (default: the cwd's main checkout)")
    ap.add_argument(
        "--config-dir", help="CLAUDE_CONFIG_DIR for the reviewer (default: $CLAUDE_CONFIG_DIR or ~/.claude)"
    )
    ap.add_argument("--context", default="", help="PR-specific context appended to the brief")
    ap.add_argument("--timeout", type=float, default=45, metavar="MIN")
    ap.add_argument("--keep", action="store_true", help="keep the workspace and worktree after success")
    ap.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT)
    args = ap.parse_args(argv)
    try:
        return spawn(args)
    except SpawnError as exc:
        log(f"FATAL {exc}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
