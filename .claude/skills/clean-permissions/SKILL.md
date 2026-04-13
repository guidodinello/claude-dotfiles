---
name: clean-permissions
description: Cleans up .claude/settings.local.json or settings.json by generalizing overly-specific Bash permission rules, removing hardcoded paths, ensuring Read(./**) is present, and flagging write-capable commands. Use this skill whenever the user asks to clean up, tidy, fix, or simplify their Claude Code permissions or settings file, or when settings.local.json has accumulated specific paths or one-off commands that should be generalized.
---

# Clean Permissions

Tidy up a Claude Code settings file so permission rules are general and maintainable
rather than littered with hardcoded paths and one-off invocations.

## What this skill does

1. Finds and reads the settings file
2. Ensures `Read(./**)` is in the allow list
3. Detects overly-specific `Bash(...)` rules and generalizes them
4. Deduplicates rules that collapse to the same form
5. Flags write-capable commands and discusses safer alternatives with the user
6. Shows a summary of changes and confirms before writing

## Step 0 — Fetch current permissions docs

Before auditing, use the `claude-code-guide` agent to fetch the latest Claude Code
permissions documentation. Ask it specifically about:
- The syntax for `Bash(...)`, `Read(...)`, and `WebFetch(...)` rules
- Wildcard semantics (`*` vs `**`, `:*` suffix)
- Any new rule types or patterns added since your knowledge cutoff

This ensures the generalizations you suggest reflect the current permission model,
not a stale snapshot.

## Step 1 — Find the settings file

Check in order:
- `.claude/settings.local.json` (preferred — local overrides)
- `.claude/settings.json` (shared project settings)

Read and parse the JSON.

## Step 2 — Audit each allow rule

### Read rules
If `Read(./**)` is missing, add it. It covers all file reads in the project and
eliminates the need for most `Bash(cat/grep/find ...)` read-only pipelines.

Keep other `Read(...)` and `WebFetch(...)` rules as-is — domain allowlists and
scoped paths are intentionally specific.

### Bash rules
A rule is **overly specific** if it contains any of:
- An absolute path: `/home/...`, `/Users/...`, `~/...`
- A long specific argument list with filenames or patterns baked in
- A one-time invocation that could be expressed as `Bash(command:*)`

To generalize: extract the first word (the command) and replace with `Bash(command:*)`.

**Examples:**
```
Bash(grep -n "sys.path" /home/guido/project/**/*.py)  →  Bash(grep:*)
Bash(find /home/guido/project -type f -exec wc -l {} +)  →  remove (Read covers it)
Bash(ls -la /home/guido/project/checkpoints/*.zip)  →  Bash(ls:*)
Bash(tail -50 /home/guido/project/logs/train.log)  →  Bash(tail:*)
Bash(awk '{print $1, $2}')  →  Bash(awk:*)
Bash(python3 -c "import foo; ...")  →  remove (prefer uv run python)
```

After generalization, remove duplicates — if multiple rules collapse to the same
`Bash(command:*)`, keep only one.

## Step 3 — Flag write-capable commands

Some commands can write or delete files. After generalizing, check for these and
discuss with the user before writing:

| Rule | Risk | Recommendation |
|------|------|----------------|
| `Bash(tee:*)` | Always writes to a file | Scope to a directory: `Bash(tee logs/*)` |
| `Bash(find:*)` | `-delete`, `-exec rm/mv/cp` are possible | Remove if `Read(./**)` covers the use case |
| `Bash(awk:*)` | Can redirect output with `> file` | Low risk; note it and keep unless user objects |
| `Bash(sed:*)` | `-i` edits files in-place | Flag; consider removing |
| `Bash(rm:*)`, `Bash(mv:*)`, `Bash(cp:*)` | Destructive | Flag and recommend removing |
| `Bash(python3:*)` | Can do anything | Prefer `Bash(uv run:*)` in uv-managed projects |

Present the flags clearly before writing so the user can decide.

## Step 4 — Show the diff and confirm

Present a clean summary:

```
Removing (overly specific):
  - Bash(grep -n "foo" /home/user/project/file.py)
  - Bash(ls -la /home/user/project/checkpoints/*.zip)

Collapsing to generic:
  + Bash(grep:*)
  + Bash(ls:*)

Adding (missing):
  + Read(./**)

Keeping unchanged:
  WebFetch(domain:es.wikipedia.org)
  Bash(uv run:*)
  ...

⚠️  Write-capable commands to review:
  Bash(tee:*) — tee always writes; consider scoping to Bash(tee logs/*)
```

Ask the user to confirm or adjust before writing anything.

## Step 5 — Write back

Write the cleaned JSON to the same file, pretty-printed with 2-space indentation.
