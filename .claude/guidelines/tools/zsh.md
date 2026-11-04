## Shell is zsh

The Bash tool runs zsh, not bash. zsh does not word-split an unquoted variable (no `SH_WORD_SPLIT`), so `c="aws --profile x"; $c ...` runs a command literally named `aws --profile x` and fails.

- Never keep a command or its flags in a string variable and expand it unquoted.
- Use an array, which works in both shells: `cmd=(aws --profile x); "${cmd[@]}" s3 ls`.
- Or use a function: `awsx() { aws --profile x "$@"; }`.
