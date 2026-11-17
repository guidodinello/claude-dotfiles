#!/usr/bin/env bash
# PreToolUse guard for the file tools (Read, Edit, Write, NotebookEdit, Grep).
# Blocks (exit 2) any file whose basename is an env file, anywhere on disk,
# unless it is an example: .env.example, .env.*.example, .env.sample,
# .env.template. An env file is a basename that starts with `.env` (.env,
# .env.local, .env.backup, .envrc, ...) or ends in `.env` (prod.env).
#
# Why a hook and not only deny rules: a bare `Read(.env*)` rule anchors at the
# current directory, a `!` carve-out cannot reach a `//` or `~/` anchored rule,
# so the deny rules in settings.base.json can only list real-file names outside
# the project. This hook is the fail-closed layer for every other name.
#
# Like guard-bash.sh, this is a policy control, so it fails closed: if the hook
# input cannot be read, or has no usable path, the call is blocked.
#
# Grep: only a `path` that is itself an env file is blocked. A directory (or no
# path, which means the current directory) is allowed: the guard cannot see
# inside the search, so the deny rules cover in-project content.

block() {
  echo "BLOCKED: $*" >&2
  exit 2
}

input="$(cat)"
if ! tool="$(jq -er '.tool_name | select(type == "string")' 2>/dev/null <<<"${input}")"; then
  block "guard-env-files.sh could not read .tool_name from the hook input (is jq installed?). Refusing to run unchecked."
fi

if [[ "${tool}" == "Grep" ]]; then
  # No path means the current directory: nothing to judge here.
  kind="$(jq -r '.tool_input.path | type' <<<"${input}" 2>/dev/null)" || block "guard-env-files.sh could not read .tool_input.path from the hook input."
  [[ "${kind}" == "null" ]] && exit 0
  [[ "${kind}" == "string" ]] || block "Grep path is not a string; cannot tell what it searches."
  path="$(jq -r '.tool_input.path' <<<"${input}")"
  # Grep over a directory is not a read of an env file.
  [[ -z "${path}" || -d "${path}" ]] && exit 0
else
  if ! path="$(jq -er '(.tool_input.file_path // .tool_input.notebook_path) | select(type == "string" and length > 0)' 2>/dev/null <<<"${input}")"; then
    block "guard-env-files.sh could not read a file path from the hook input. Refusing to run unchecked."
  fi
fi

# 0 when the basename of $1 is an env file that is not an example. Lowercased
# first: macOS volumes are case-insensitive, so `.ENV` is the same file.
is_env_file() {
  local p="$1" name
  while [[ "${p}" == */ && "${p}" != "/" ]]; do p="${p%/}"; done
  name="$(printf '%s' "${p##*/}" | tr '[:upper:]' '[:lower:]')"
  case "${name}" in
    .env.example | .env.*.example | .env.sample | .env.template) return 1 ;;
    .env* | *.env) return 0 ;;
  esac
  return 1
}

# The path itself, then each hop of a symlink chain: a link named `notes` that
# points at `.env` reads the env file.
current="${path}"
for ((hop = 0; hop < 40; hop++)); do
  if is_env_file "${current}"; then
    block "${current##*/} is an env file. Real env files hold secrets and stay off-limits; the example files (.env.example, .env.*.example, .env.sample, .env.template) are allowed. Ask the user to read or change it."
  fi
  [[ -L "${current}" ]] || break
  target="$(readlink "${current}")" || break
  [[ "${target}" == /* ]] || target="${current%/*}/${target}"
  current="${target}"
done

exit 0
