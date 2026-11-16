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
