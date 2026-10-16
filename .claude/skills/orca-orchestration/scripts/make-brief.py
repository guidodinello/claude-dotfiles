#!/usr/bin/env python3
"""Write <worktree>/.task-brief.md for one implementer session.

usage: make-brief.py <run-dir> <task-key>

Template: copy it into the run folder and adjust it if a project needs more. Inputs, all
inside the per-project docs folder (<docs>/runs/<run>/ is the run dir):

  <run>/ids.json              run and task ids (shape below)
  <run>/task-<key>.md         the task body, verbatim (or set task_read_command)
  <run>/parent.md             the parent story body, verbatim (optional)
  <run>/notes-common.md       coordination notes for every worker (optional)
  <run>/notes-<key>.md        coordination notes for this worker (optional)
  <docs>/brief-rules/common.md   rules for every brief (optional)
  <docs>/brief-rules/<repo>.md   per-repo rules: stack commands, checks, hooks (optional)

ids.json:
  {
    "read_first": ["/abs/path/CLAUDE.md"],
    "base_branch": "main",
    "base_sha": "<sha of base when the run started>",
    "integration_branch": "feature/<id>/<slug>",      # null when PRs target base
    "merged": ["<branch or PR merged into the integration branch so far>"],
    "task_read_command": ["<tracker-cli>", "read", "{id}"],   # optional
    "tasks": {
      "<key>": {"id": "<task id>", "title_prefix": "[<task id>]", "repo": "<repo>",
                "worktree": "/abs/worktree", "branch": "<type>/<id>/<slug>",
                "stack_on": ["origin/<reviewed unmerged sibling>"]}
    }
  }
"""
import json
import subprocess
import sys
from pathlib import Path


def read(path):
    return path.read_text().strip() if path.is_file() else ""


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    run = Path(sys.argv[1]).resolve()
    key = sys.argv[2]
    docs = run.parent.parent
    ids = json.loads((run / "ids.json").read_text())
    t = ids["tasks"][key]
    wt = Path(t["worktree"])

    branch = subprocess.check_output(["git", "-C", str(wt), "branch", "--show-current"], text=True).strip()
    if branch != t["branch"]:
        sys.exit(f"branch mismatch in {wt}: {branch} != {t['branch']} (rename it before writing the brief)")

    task_body = read(run / f"task-{key}.md")
    if not task_body and ids.get("task_read_command"):
        cmd = [part.replace("{id}", t["id"]) for part in ids["task_read_command"]]
        task_body = subprocess.check_output(cmd, text=True).strip()
    if not task_body:
        sys.exit(f"no task body: write {run}/task-{key}.md or set task_read_command")

    pr_base = ids.get("integration_branch") or ids["base_branch"]
    merged = ", ".join(ids.get("merged") or []) or "none"
    read_first = "\n".join(f"- `{p}` in full (not auto-loaded from a worktree)." for p in ids.get("read_first", []))
    stack = t.get("stack_on") or []
    step0 = ""
    if stack:
        merges = "\n".join(f"git merge --no-ff {ref}" for ref in stack)
        step0 = (
            "\n## Step 0, before anything else\n\n"
            "Merge the reviewed, not yet merged sibling(s) you depend on, with a merge commit (never rebase):\n\n"
            f"```bash\ngit fetch origin\n{merges}\n```\n\n"
            f"Your PR base stays `{pr_base}`.\n"
        )

    notes = "\n\n".join(n for n in (read(run / "notes-common.md"), read(run / f"notes-{key}.md")) if n)
    if notes:
        notes = "## Coordination notes\n\n" + notes

    sections = [
        f"# Task brief: {t['id']} ({t['repo']})",
        "You are an implementer session coordinated by an orchestrator session. Work only in this worktree.",
        "## Your loop\n\n"
        "1. You start in plan mode. Investigate, then write your implementation plan with an explicit "
        "**Open questions** section (\"None\" if none). No code until the orchestrator approves.\n"
        "2. When the orchestrator says to read `.orchestrator-answers.md`, fold every answer into the plan and "
        "present it again.\n"
        "3. After approval: implement, run the checks, commit, push, open the PR.\n"
        "4. Reply with the PR URL.",
        "## Read first\n\n" + (read_first or "- This repo's own `CLAUDE.md` / `AGENTS.md`, if present."),
        f"## Baseline\n\nBranch `{branch}` = `{pr_base}` at start ({ids.get('base_sha', '?')}) plus these merged "
        f"siblings: {merged}. Treat paths and names in the task as leads to confirm against the code; "
        "tasks drafted before sibling work landed can carry stale names.",
        step0.strip(),
        notes,
        "## Git and PR rules (hard)\n\n"
        f"- Branch is set: `{branch}`. Do not rename it.\n"
        f"- PR base: `{pr_base}`.\n"
        f"- PR title: `{t.get('title_prefix', '')} <short title>`. Reference only this task's id in the body.\n"
        "- Never `--no-verify`. If a hook fails on something you did not touch, ask instead.\n"
        "- `git status` before every commit. Never commit `.task-brief.md` or `.orchestrator-answers.md`.",
        read(docs / "brief-rules" / "common.md"),
        read(docs / "brief-rules" / f"{t['repo']}.md"),
        f"## Your task ({t['id']})\n\n{task_body}",
    ]
    parent = read(run / "parent.md")
    if parent:
        sections.append(f"## Parent story, for context\n\n{parent}")

    brief = "\n\n".join(s for s in sections if s) + "\n"
    (wt / ".task-brief.md").write_text(brief)
    print(f"wrote {wt}/.task-brief.md ({len(brief.splitlines())} lines)")


if __name__ == "__main__":
    main()
