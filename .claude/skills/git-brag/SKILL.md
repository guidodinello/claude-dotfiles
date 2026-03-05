---
name: git-brag
description: Find all commits made by the current git user that touched a given path, formatted for a brag/perf-review doc
---

# Git Brag Skill

Find commits you authored that touched specific files or folders. Useful for perf reviews, brag docs, or auditing your contributions to documentation.

## Instructions

The user may optionally specify a path or glob (e.g. `/git-brag .github/instructions/`). If no path is given, default to `.github/instructions/`.

### Step 1 — Resolve identity and path

Run these two commands in parallel:

```bash
git config user.name && git config user.email
```

Use the returned name as the `--author` filter. Use the user-supplied path (or `.github/instructions/` as default).

### Step 2 — Find matching commits

```bash
git log --author="<name>" --format="%H %ai %s" -- "<path>"
```

### Step 3 — Expand each commit

For each commit hash returned, run in parallel:

```bash
git diff-tree --no-commit-id -r --name-only <hash>
```

Filter the output to only lines that start with the searched path, so you show only the relevant files changed per commit (the commit may have touched other files too).

### Step 4 — Format for brag doc

Present results as a clean markdown list ready to paste into a perf review doc:

```
Found N commits touching `<path>`:

- **[TICKET] Commit subject** (`shortHash`) — YYYY-MM-DD
  - `path/to/file.md`
  - `path/to/other.md`
```

If no commits are found, say so clearly and suggest broadening the path.

### Step 5 — Offer follow-up

After listing results, offer to:

- Show the full diff of any specific commit (`git show <hash> -- <path>`)
- Broaden the search to a different path
- Filter by date range (e.g. "last 6 months") using `--after` / `--before`
