#!/usr/bin/env python3
"""Parse a raw opencode review transcript for FINDING blocks and post it as a
GitHub PR review with inline comments, matching the user's preferred
code-review skill's format (blocking/non-blocking tiers, full-SHA permalinks,
harness/model attribution).

Usage: post_structured_review.py <repo-dir> <pr-number> <model> <raw-review-file>
"""
import json
import posixpath
import re
import subprocess
import sys

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
FINDING_RE = re.compile(r"---FINDING-START---(.*?)---FINDING-END---", re.DOTALL)
DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def gh_json(repo_dir, *args):
    result = subprocess.run(["gh", *args], cwd=repo_dir, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def normalize_path(path: str) -> str:
    path = path.strip().strip("`")
    for prefix in ("a/", "b/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
    return posixpath.normpath(path) if path else path


def commentable_lines(diff_text: str) -> dict[str, set[int]]:
    """New-side line numbers GitHub accepts an inline comment on (added and context lines)."""
    lines_by_file: dict[str, set[int]] = {}
    current: set[int] | None = None
    new_line = 0
    for line in diff_text.splitlines():
        if file_match := DIFF_FILE_RE.match(line):
            current = lines_by_file.setdefault(file_match.group(1), set())
        elif line.startswith("+++ /dev/null"):
            current = None
        elif hunk_match := HUNK_RE.match(line):
            new_line = int(hunk_match.group(1))
        elif current is not None and line.startswith(("+", " ")) and not line.startswith("+++"):
            current.add(new_line)
            new_line += 1
    return lines_by_file


def parse_findings(text):
    text = ANSI_RE.sub("", text)
    findings = []
    for block in FINDING_RE.findall(text):
        tier = re.search(r"TIER:\s*(blocking|non-blocking)", block, re.IGNORECASE)
        file_ = re.search(r"FILE:\s*(.+)", block)
        line_ = re.search(r"LINE:\s*(\d+)", block)
        body_ = re.search(r"BODY:\s*(.+)", block, re.DOTALL)
        if not (tier and file_ and line_ and body_):
            continue
        findings.append(
            {
                "tier": tier.group(1).lower(),
                "file": normalize_path(file_.group(1)),
                "line": int(line_.group(1)),
                "body": body_.group(1).strip().splitlines()[0].strip(),
            }
        )
    return findings


def attribution(model):
    if model.startswith("claude"):
        return f"\U0001f916 Generated with Claude Code CLI, model `{model}`."
    return f"\U0001f916 Generated with OpenCode CLI, model `opencode/{model}`."


def permalink(owner_repo, sha, path, line):
    start = max(1, line - 1)
    end = line + 1
    return f"https://github.com/{owner_repo}/blob/{sha}/{path}#L{start}-L{end}"


def main():
    repo_dir, pr_number, model, raw_file = sys.argv[1:5]

    with open(raw_file, encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    findings = parse_findings(raw_text)

    owner_repo = gh_json(repo_dir, "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
    head_sha = gh_json(repo_dir, "pr", "view", pr_number, "--json", "headRefOid", "-q", ".headRefOid")

    n_blocking = sum(1 for x in findings if x["tier"] == "blocking")
    n_non_blocking = sum(1 for x in findings if x["tier"] == "non-blocking")

    if not findings:
        body = (
            "### Code review\n\n"
            # Verbatim from code-review/SKILL.md's own no-issues template —
            # keep in sync by hand; only the false-positive list is read at runtime.
            "No issues found. Checked for bugs and CLAUDE.md compliance.\n\n"
            + attribution(model)
        )
        comments = []
    else:
        # GitHub rejects the whole review if any inline comment points outside
        # the diff, so those findings go in the body instead of sinking the rest.
        anchorable = commentable_lines(gh_json(repo_dir, "pr", "diff", pr_number))
        comments = []
        unanchored = []
        for finding in findings:
            link = permalink(owner_repo, head_sha, finding["file"], finding["line"])
            tag = f"**[{finding['tier']}]**"
            if finding["line"] in anchorable.get(finding["file"], set()):
                comments.append(
                    {
                        "path": finding["file"],
                        "line": finding["line"],
                        "side": "RIGHT",
                        "body": f"{tag} {finding['body']}\n\n{link}",
                    }
                )
            else:
                unanchored.append(
                    f"- {tag} `{finding['file']}:{finding['line']}`: {finding['body']}\n  {link}"
                )
        outside_diff = (
            "Outside the diff (no inline anchor):\n\n" + "\n".join(unanchored) + "\n\n"
            if unanchored
            else ""
        )
        body = (
            "### Code review\n\n"
            f"Found {n_blocking} blocking issue(s) and {n_non_blocking} non-blocking note(s).\n\n"
            + outside_diff
            + attribution(model)
        )

    payload = {"commit_id": head_sha, "body": body, "event": "COMMENT", "comments": comments}

    subprocess.run(
        ["gh", "api", f"repos/{owner_repo}/pulls/{pr_number}/reviews", "--method", "POST", "--input", "-"],
        cwd=repo_dir,
        input=json.dumps(payload),
        text=True,
        check=True,
    )

    print(f"Posted review: {n_blocking} blocking, {n_non_blocking} non-blocking, model={model}", file=sys.stderr)


if __name__ == "__main__":
    main()
