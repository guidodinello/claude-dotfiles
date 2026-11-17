## Shell is zsh

The Bash tool runs zsh, not bash. zsh does not word-split an unquoted variable (no `SH_WORD_SPLIT`), so `c="aws --profile x"; $c ...` runs a command literally named `aws --profile x` and fails.

- Never keep a command or its flags in a string variable and expand it unquoted.
- Use an array, which works in both shells: `cmd=(aws --profile x); "${cmd[@]}" s3 ls`.
- Or use a function: `awsx() { aws --profile x "$@"; }`.

## Pipelines hide failures

Never pipe `git commit`, `git push`, `gh api` writes or `gh pr` writes (`create`, `merge`, `edit`, `comment`, `review`, `close`) into `tail` or `head`. Read-only `gh pr view` / `gh pr diff` are fine to pipe. The pipeline's exit status is `tail`'s, so a hook rejection or CLI error looks like success.

- Run them unpiped, or
- put `set -o pipefail` in the same command: `set -o pipefail; git commit ... | tail -5` (shell state does not persist between Bash tool calls), or
- append `; echo exit=$?` to the unpiped command (after a pipe it reports `tail`'s status, not the command's).

## zsh expands more than bash

An unquoted word is expanded before the command runs, and a failed expansion aborts the whole command (and the rest of a `&&` chain).

- **Globs fail when nothing matches** (`zsh: no matches found`). Quote any pattern meant for the program: `grep --include='*.ts'`, `find -name '*.md'`. For a glob that may match nothing, add the `(N)` qualifier (`rm -f x-*(N)`) or use `find`.
- **A word starting with `=` is a command lookup**: `echo =====` fails with `===== not found`. Quote separators: `echo '====='`.
- **`?` is a glob too**: quote URLs with a query string, `curl 'https://host/path?a=1&b=2'`.

## macOS ships BSD tools

- `sed -i` needs a suffix argument: `sed -i '' 's/a/b/' f`. GNU's `sed -i 's/a/b/' f` fails.
- There is no `timeout`. Use `gtimeout` (coreutils) if installed, or the tool's own timeout flag.
