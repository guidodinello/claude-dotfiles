---
name: code-review
description: >
  Code review a pull request. Multi-agent review with confidence scoring —
  checks CLAUDE.md compliance, bugs, git history, previous PR comments, and
  code comment guidance. Posts blocking findings and a separate non-blocking
  section on the PR.
---

Provide a code review for the given pull request.

To do this, follow these steps precisely:

1. Use a Haiku agent to check if the pull request (a) is closed, (b) is a draft, or (c) does not need a code review (eg. because it is an automated pull request, or is very simple and obviously ok). If so, do not proceed. Do NOT skip based on a prior review already existing on the PR (including one from you) — multiple independent reviews (eg. from different models/harnesses run in parallel) are expected and each should post its own findings.
2. Use another Haiku agent to give you a list of file paths to (but not the contents of) any relevant CLAUDE.md files from the codebase: the root CLAUDE.md file (if one exists), as well as any CLAUDE.md files in the directories whose files the pull request modified
3. Use a Haiku agent to view the pull request, and ask the agent to return a summary of the change
4. Then, launch 5 parallel Sonnet agents to independently code review the change. The agents should do the following, then return a list of issues and the reason each issue was flagged (eg. CLAUDE.md adherence, bug, historical git context, etc.):
   a. Agent #1: Audit the changes to make sure they comply with the CLAUDE.md. Note that CLAUDE.md is guidance for Claude as it writes code, so not all instructions will be applicable during code review.
   b. Agent #2: Read the file changes in the pull request, then do a shallow scan for obvious bugs. Avoid reading extra context beyond the changes, focusing just on the changes themselves. Focus on large bugs, and avoid small issues and nitpicks. Ignore likely false positives.
   c. Agent #3: Read the git blame and history of the code modified, to identify any bugs in light of that historical context
   d. Agent #4: Read previous pull requests that touched these files, and check for any comments on those pull requests that may also apply to the current pull request.
   e. Agent #5: Read code comments in the modified files, and make sure the changes in the pull request comply with any guidance in the comments.
5. For each issue found in #4, launch a parallel Haiku agent that takes the PR, issue description, and list of CLAUDE.md files (from step 2), and returns a score to indicate the agent's level of confidence for whether the issue is real or false positive. To do that, the agent should:
   - **Always start by fetching the PR diff** using `gh pr diff <PR_NUMBER> --repo <OWNER>/<REPO>` as the primary source of truth for what code is being reviewed. The code described in the issue may be newly introduced by this PR and therefore not present in the local filesystem yet — absence from local files is NOT evidence of a false positive.
   - Verify whether the specific code pattern described in the issue actually appears in the PR diff. If it does, treat it as confirmed and score accordingly.
   - Only use local file reads to gather additional context (e.g. CLAUDE.md contents, existing patterns, proxy config) — not to verify the existence of new code being added.
   - For issues flagged due to CLAUDE.md instructions, double check that the CLAUDE.md actually calls out that issue specifically.

   The agent should score each issue on a scale from 0-100. The scale is (give this rubric to the agent verbatim):
   a. 0: Not confident at all. This is a false positive that doesn't stand up to light scrutiny, or is a pre-existing issue.
   b. 25: Somewhat confident. This might be a real issue, but may also be a false positive. The agent wasn't able to verify that it's a real issue. If the issue is stylistic, it is one that was not explicitly called out in the relevant CLAUDE.md.
   c. 50: Moderately confident. The agent was able to verify this is a real issue, but it might be a nitpick or not happen very often in practice. Relative to the rest of the PR, it's not very important.
   d. 75: Highly confident. The agent double checked the issue, and verified that it is very likely it is a real issue that will be hit in practice. The existing approach in the PR is insufficient. The issue is very important and will directly impact the code's functionality, or it is an issue that is directly mentioned in the relevant CLAUDE.md.
   e. 100: Absolutely certain. The agent double checked the issue, and confirmed that it is definitely a real issue, that will happen frequently in practice. The evidence directly confirms this.
6. Triage issues into two tiers. The primary axis is **whether the scoring agent verified the issue is real**, not the raw number — discrete rubric anchors (0/25/50/75/100) make agents snap to round scores, so a genuinely-verified-but-minor finding can land at 40 and wrongly get dropped. Avoid that. Do not silently discard verified findings — that loses real signal.
   - **Blocking (verified real AND important — typically score >= 70)**: real issues that should be addressed before merge.
   - **Non-blocking (verified real but minor/low-frequency/low-impact)**: the scoring agent confirmed the issue exists but judged it unimportant. **Any finding the agent explicitly verified as real belongs here at minimum, regardless of its numeric importance score** (even if it scored below 50). The rubric's anchor for 50 is "able to verify this is a real issue, but it might be a nitpick" — treat verification, not the number, as the gate. Surface these in a clearly-labelled non-blocking section so the author can decide.
   - **Drop (not verified)**: the agent could not confirm the issue is real — unverified, likely false positives, or pre-existing issues. Discard these.

   If there are no verified issues at all (blocking or non-blocking), do not proceed.

   Note: the "Real issues, but on lines the user did not modify" false-positive rule still applies and trumps the tiers — such an issue is out of scope for the PR review regardless of verification. If it is a genuine problem worth tracking, mention it once in the non-blocking section (or suggest filing an issue) rather than as an inline comment on unmodified lines.
7. Use a Haiku agent to repeat the eligibility check from #1 (closed/draft/doesn't-need-review only — still not the "already reviewed" case), to make sure the pull request hasn't been closed or converted to a draft since step 1.
8. Finally, post the findings as a **PR review with inline comments** (not a top-level issue comment). This makes findings discoverable by automated tools that read `pulls/{pr}/comments`.

   a. Get the head commit SHA: `gh pr view <PR> --json headRefOid --jq '.headRefOid'`
   b. Map **every** verified finding — both blocking and non-blocking — to its `path` (repo-relative file path) and `line` (line number in the file on the RIGHT/new side). All findings become inline thread comments. The review `body` is just a summary header.
   c. Post a single review via the GitHub API using JSON input:

   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews \
     --method POST \
     --input - <<'EOF'
   {
     "commit_id": "<head_sha>",
     "body": "### Code review\n\nFound N blocking issue(s) and M non-blocking note(s).\n\n🤖 Generated with <harness name>, model `<model id>`.",
     "event": "COMMENT",
     "comments": [
       {
         "path": "path/to/file.py",
         "line": 42,
         "side": "RIGHT",
         "body": "**[blocking]** Brief description. (CLAUDE.md says \"...\")\n\nhttps://github.com/{owner}/{repo}/blob/{sha}/path/to/file.py#L41-L43"
       },
       {
         "path": "path/to/other.py",
         "line": 17,
         "side": "RIGHT",
         "body": "**[non-blocking]** Brief description. Verified real but low-impact (<reason>).\n\nhttps://github.com/{owner}/{repo}/blob/{sha}/path/to/other.py#L16-L18"
       }
     ]
   }
   EOF
   ```

   d. If a finding cannot be mapped to a specific line (e.g. it spans multiple files with no single anchor), include it in the review `body` instead of as an inline comment.
   e. If there are no verified findings at all, post the "No issues found" review (see below).
   f. After the review is posted (either path), swap the PR's labels: `gh pr edit <PR_NUMBER> --remove-label "pending-review" --add-label "reviewed"`. If the PR doesn't have the `pending-review` label (e.g. it wasn't opened via the feature-workflow skill), it's fine for `--remove-label` to no-op — still add `reviewed`.

   Keep each inline comment body brief. Avoid emojis. Include the permalink to the relevant lines in the comment body.

Examples of false positives, for steps 4 and 5:

- Pre-existing issues
- Something that looks like a bug but is not actually a bug
- Pedantic nitpicks that a senior engineer wouldn't call out
- Issues that a linter, typechecker, or compiler would catch (eg. missing or incorrect imports, type errors, broken tests, formatting issues, pedantic style issues like newlines). No need to run these build steps yourself -- it is safe to assume that they will be run separately as part of CI.
- General code quality issues (eg. lack of test coverage, general security issues, poor documentation), unless explicitly required in CLAUDE.md
- Issues that are called out in CLAUDE.md, but explicitly silenced in the code (eg. due to a lint ignore comment)
- Changes in functionality that are likely intentional or are directly related to the broader change
- Real issues, but on lines that the user did not modify in their pull request

Notes:

- Do not check build signal or attempt to build or typecheck the app. These will run separately, and are not relevant to your code review.
- Use `gh` to interact with Github (eg. to fetch a pull request, or to create inline comments), rather than web fetch
- Make a todo list first
- You must cite and link each bug (eg. if referring to a CLAUDE.md, you must link it)
- For each inline comment, use this format:

```
<brief description of bug> (<source>: "<relevant quote or rule>")

https://github.com/{owner}/{repo}/blob/{full_sha}/{path}#L{start}-L{end}
```

- The review body (top-level text of the review) should be:

```
### Code review

Found N blocking issue(s) and M non-blocking note(s).

🤖 Generated with <harness name>, model `<model id>`.
```

  Replace `<harness name>` and `<model id>` with the identity of the coding agent/CLI and model actually running this skill (e.g. "OpenCode, model `opencode/deepseek-v4-flash-free`", "Kiro CLI, model `claude-opus-4.8`") — never hardcode "Claude Code". If you cannot determine the model id, use the harness name alone: "🤖 Generated with <harness name>."

- Each inline comment should be prefixed with its tier: `**[blocking]**` or `**[non-blocking]**`. This lets the author see priority at a glance without needing to read the full review body.

- Or, if you found no issues, post a review with this body and no inline comments:

```
### Code review

No issues found. Checked for bugs and CLAUDE.md compliance.

🤖 Generated with <harness name>, model `<model id>`.
```

- When linking to code, follow the following format precisely, otherwise the Markdown preview won't render correctly: <https://github.com/anthropics/claude-cli-internal/blob/c21d3c10bc8e898b7ac1a2d745bdc9bc4e423afe/package.json#L10-L15>
  - Requires full git sha
  - You must provide the full sha. Commands like `https://github.com/owner/repo/blob/$(git rev-parse HEAD)/foo/bar` will not work, since your comment will be directly rendered in Markdown.
  - Repo name must match the repo you're code reviewing

  - # sign after the file name

  - Line range format is L[start]-L[end]
  - Provide at least 1 line of context before and after, centered on the line you are commenting about (eg. if you are commenting about lines 5-6, you should link to `L4-7`)
