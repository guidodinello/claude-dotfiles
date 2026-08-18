---
paths:
  - "**/*.sh"
  - "**/*.bash"
---

<!-- Code examples and table rows can't be rewrapped without breaking them;
     prose is held to 80 columns. This directive travels with the file so it
     lints clean in any repo that vendors it. Claude Code strips block HTML
     comments before injection, so this costs no context. -->
<!-- markdownlint-configure-file {
  "MD013": { "code_blocks": false, "tables": false }
} -->

# Shell — Agent Code Guidelines

General-purpose guidelines for shell scripts where AI agents assist with
development. As a path-scoped rule it self-loads on `.sh` / `.bash` — never
copy it into a project's `CLAUDE.md`. Adapt the project-specific sections at
the bottom when adopting it in a new project.

Deliberately not globbed: `.bashrc`/`.zshrc`. `.zshrc` is zsh, and this file
is bash guidance — array indexing and word-splitting defaults differ. More
importantly, this file's headline recommendation (`set -euo pipefail`) must
never go into an interactive rc file.

---

## Philosophy

- **Explicit is better than implicit** — no magic, no hidden state, no
  surprising side-effects. If a line does something non-obvious, a comment
  should say so.
- **Simple is better than complex** — shell rewards small, composable
  scripts far more than it rewards clever one-liners.
- **Readability counts** — code is read far more often than it is written.
  Optimise for the reader.
- **Errors should never pass silently** — fail loudly and early. Don't let
  a failed command continue as if nothing happened.
- **When not to write shell.** Google's Shell Style Guide is explicit here:
  *"Shell should only be used for small utilities or simple wrapper
  scripts"* — and *"if you are writing a script that is more than 100 lines
  long, or that uses non-straightforward control flow logic, you should
  rewrite it in a more structured language now."* The test: once a script
  needs real data structures, error types, or a test suite, it has outgrown
  the language.

---

## Software engineering principles

### YAGNI — You Aren't Gonna Need It

Don't add flags, config files, or option parsing for hypothetical future
use. Build what the task actually needs. If the requirement arrives later,
add it then.

```bash
# Bad — parameterised "for future flexibility" nobody has asked for
sync() {
  local mode="${1:-full}" dry_run="${2:-false}" verbose="${3:-false}"
  ...
}

# Good — add parameters when there's an actual reason to vary them
sync() {
  local mode="${1:-full}"
  ...
}
```

### DRY — Don't Repeat Yourself (but don't over-apply it)

Duplicate code is a maintenance hazard. Extract a shared function — but only
once you see the same thing repeated at least three times and are confident
the repetition isn't coincidental.

### SSOT — Single Source of Truth

Every piece of knowledge — a path, a version pin, a list of targets — should
have exactly one authoritative definition.

```bash
# Bad — the same directory list appears in two places and will drift
for d in api web worker; do lint "$d"; done
for d in api web worker; do test "$d"; done

# Good — one definition; everything derives from it
targets=(api web worker)
for d in "${targets[@]}"; do lint "$d"; done
for d in "${targets[@]}"; do test "$d"; done
```

The test: if renaming or removing one thing requires finding and updating a
second place, you have two sources of truth.

### KISS — Keep It Simple

Prefer a flat script over nested functions calling functions. Prefer a
readable `if` chain over a dense one-liner built from pipes and flags.
Each layer of indirection has a cost in a language with weak tooling
support for tracing it.

### Single responsibility

Each function should do one thing. If a function's name needs "and",
consider splitting it.

```bash
# Bad — the name has to say "and", revealing two responsibilities
validate_and_deploy() { ... }

# Good — each function has one job and a name that fits it exactly
validate() { ... }
deploy() { ... }
```

### Locality of Behavior

Code that changes together should live together. Define a variable near the
code that uses it, not in a shared "config" block at the top that has grown
to hold everything.

The test: if understanding one behavior requires opening more than two
files, the behavior has too much distance.

### Fail fast

Validate arguments and required environment at the top of the script.
Inside the script, let an unexpected failure stop execution rather than
limping on with a partially-failed state.

```bash
# Bad — continues with an empty $target and silently does nothing useful
target="${1}"
rsync -a "$src/" "$target/"

# Good — caller learns about the problem immediately
target="${1:?usage: $0 <target>}"
rsync -a "$src/" "$target/"
```

---

## Shebang and portability

Use `#!/usr/bin/env bash` for anything using bash-only features (arrays,
`[[ ]]`, `local`, `${var,,}`). Use `#!/bin/sh` only for scripts that are
genuinely POSIX-compliant — never write a bashism under a `sh` shebang and
assume it will work everywhere `sh` runs.

---

## `set -euo pipefail` — default, with caveats

Set it at the top of a standalone script:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

`-e` (errexit) is a useful backstop but not a safety net — the BashFAQ
"why not set -e" entry documents at length where it silently does nothing:

| Context | Does errexit apply? |
| ------ | ------- |
| `if cmd`, `cmd && ...`, `cmd \|\| ...` | No |
| A command inside a function called as a conditional | No |
| A failing command isn't the *last* one inside `$(...)`, e.g. `x=$(fail; echo ok)` (fixed by `shopt -s inherit_errexit`, bash 4.4+) | No |
| `local x=$(fail)` — `local`'s own exit status masks the substitution's, even when `fail` is the only command inside it | No |
| A non-final stage of a pipeline, without `pipefail` | No |
| Inside `<(...)`/`>(...)` process substitution | No |

`-o pipefail` closes the pipeline gap above — without it, `false \| true`
exits 0. Given the table above, check the return values of commands whose
failure you actually need to catch; don't rely on `-e` alone to catch it
for you.

**Exception — Claude Code hooks.** This repo's own convention is that a
hook must always exit 0 and never block Claude, and hooks live under
`.claude/hooks/*.sh`, which this rule's globs match. A hook does not use
bare `set -e` for that reason — errors are handled explicitly and the
script always returns 0 at the end, following the pattern in
`.claude/hooks/auto-format.sh`.

---

## Quoting

**Always quote a variable expansion** unless word-splitting or globbing is
deliberately wanted: `"${var}"`, not `$var`.

```bash
# Bad — breaks on any path containing a space
rm $file

# Good
rm "$file"
```

Use `"$@"` to forward arguments, never `$*` or an unquoted `$@` — only the
quoted form preserves each argument as a separate word.

Use an explicit path when expanding a wildcard, so a filename that happens
to start with `-` isn't read as a flag:

```bash
# Bad — a file named "-rf" here would be catastrophic
rm *

# Good
rm ./*
```

---

## `[[ ]]` over `[ ]`

`[[ ]]` avoids word splitting and pathname expansion inside the test, and
supports pattern matching (`==` with globs) and regex (`=~`) that `[ ]`
doesn't have.

```bash
# Good
if [[ -f "$path" && "$name" == *.tar.gz ]]; then

# Bad — needs manual quoting discipline `[[ ]]` gives you for free
if [ -f "$path" ] && [ "${name%.tar.gz}" != "$name" ]; then
```

---

## Command substitution

Use `$(command)`, never backtick syntax — it nests cleanly and is
unambiguous to read.

```bash
# Good
files="$(find . -name '*.log')"

# Bad
files=`find . -name '*.log'`
```

---

## Return values and `PIPESTATUS`

Check a command's exit status explicitly when its failure matters — don't
assume `set -e` caught it (see the table above).

`$?` and `PIPESTATUS` are overwritten by the very next command, so capture
them immediately:

```bash
tar czf out.tar.gz "$dir" | tee tar.log
status=("${PIPESTATUS[@]}")   # capture before anything else runs
if [[ "${status[0]}" -ne 0 ]]; then
  echo "tar failed" >&2
  exit 1
fi
```

---

## Errors to STDERR

**All error and diagnostic output goes to STDERR**, so it doesn't pollute a
script's actual output when that output is piped or captured.

```bash
err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')] $*" >&2
}

err "config file not found: $config_path"
```

---

## Arrays

Use an array for anything that is a list of items, especially a list of
command arguments — string-concatenating arguments invites quoting bugs the
moment one item contains a space.

```bash
# Bad — breaks the moment a path contains a space
opts="-rlpc --existing"
rsync $opts "$src" "$dst"

# Good
opts=(-rlpc --existing)
rsync "${opts[@]}" "$src" "$dst"
```

---

## Functions and scope

Declare every function-local variable with `local` — without it, a variable
leaks into global scope and can silently shadow or be shadowed by a
caller's variable of the same name.

Put a `main` function at the bottom holding the script's top-level flow, and
call it as the last line with `main "$@"`. This keeps the script sourceable
(for testing individual functions) without executing anything as a
side-effect of sourcing it.

---

## `eval` is banned

**Never use `eval`.** It executes a string as shell code, which makes
injection trivial the moment any part of that string comes from outside the
script, and it makes variable assignment inside it opaque to review. Use an
array, indirect parameter expansion (`${!varname}`), or a `case` statement
instead.

---

## Code smells to avoid

These patterns are warning signs that the script needs rethinking:

- **Parsing `ls` output** — filenames can contain newlines and spaces that
  break line-based parsing. Use a glob or `find … -print0` instead.

- **Unquoted command substitution in a `for` loop** — `for f in $(find ...)`
  word-splits on every space and glob-expands the result. Use `while read`
  with `find … -print0` / `read -d ''`, or a `mapfile` into an array.

- **`cat file | grep pattern`** — a useless use of `cat`; `grep pattern
  file` reads the same file with one fewer process:

  ```bash
  cat log.txt | grep ERROR   # Bad — spawns cat for nothing
  grep ERROR log.txt         # Good
  ```

- **`cd` without a failure check** — a failed `cd` leaves the script
  running in the wrong directory, silently:

  ```bash
  cd "$target"        # Bad — script continues elsewhere if this fails
  cd "$target" || exit 1   # Good
  ```

- **Temp files without `mktemp` and a cleanup trap** — a hardcoded temp
  path collides across concurrent runs and leaks a file on every failure:

  ```bash
  # Bad
  tmp=/tmp/work.txt

  # Good
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  ```

- **`rm -rf "$dir/"` where `$dir` may be unset or empty** — an unset `$dir`
  turns this into `rm -rf /`. Guard it (`: "${dir:?}"`) before any
  destructive command that interpolates a variable.

---

## Linting

**ShellCheck is recommended for all scripts, large or small** — it catches
quoting bugs, unreachable code, and portability issues that are easy to
miss by eye. `shfmt` handles formatting.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/shellcheck-py/shellcheck-py
    rev: v0.10.0.1
    hooks:
      - id: shellcheck
  - repo: https://github.com/scop/pre-commit-shfmt
    rev: v3.9.0-1
    hooks:
      - id: shfmt
```

Inline `# shellcheck disable=SC2034` is a last resort — put it directly
above the line it applies to, with a comment explaining why the warning is
a false positive here.

---

## Project-specific notes

Replace this section when adapting these guidelines for a new project.

| Item | Value |
| ------ | ------- |
| Shell | bash |
| Linter | shellcheck |
| Formatter | shfmt |
