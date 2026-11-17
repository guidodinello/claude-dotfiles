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

# Paths to judge, NUL-separated so a newline in a name cannot split one.
paths=()
if [[ "${tool}" == "Grep" ]]; then
  # No path means the current directory: nothing to judge here.
  kind="$(jq -r '.tool_input.path | type' <<<"${input}" 2>/dev/null)" || block "guard-env-files.sh could not read .tool_input.path from the hook input."
  if [[ "${kind}" != "null" ]]; then
    [[ "${kind}" == "string" ]] || block "Grep path is not a string; cannot tell what it searches."
    grep_path="$(jq -r '.tool_input.path' <<<"${input}")"
    # Grep over a directory is not a read of an env file.
    if [[ -n "${grep_path}" && ! -d "${grep_path}" ]]; then
      paths+=("${grep_path}")
    fi
  fi
  # Best effort only: a glob whose text is an env name (`.env*`, `*.env`) is
  # blocked, but a glob can spell the same files in ways this does not parse
  # (`.e*`, `.[e]nv`, `{.env,x}`), and a directory search with no glob reads them
  # anyway. It is not a guarantee, only a catch for the obvious form.
  gkind="$(jq -r '.tool_input.glob | type' <<<"${input}" 2>/dev/null)" || block "guard-env-files.sh could not read .tool_input.glob from the hook input."
  if [[ "${gkind}" != "null" ]]; then
    [[ "${gkind}" == "string" ]] || block "Grep glob is not a string; cannot tell what it searches."
    paths+=("$(jq -r '.tool_input.glob' <<<"${input}")")
  fi
else
  # Every path field the call carries is judged, whichever one the tool uses.
  # The tool schemas name file_path (Read/Edit/Write) or notebook_path
  # (NotebookEdit); a call with neither, or with a non-string one, is blocked.
  if ! jq -e '[.tool_input.file_path, .tool_input.notebook_path] | map(select(. != null)) | (length > 0) and all(type == "string" and length > 0)' <<<"${input}" >/dev/null 2>&1; then
    block "guard-env-files.sh could not read a file path from the hook input. Refusing to run unchecked."
  fi
  while IFS= read -r -d '' one; do
    paths+=("${one}")
  done < <(jq -j '[.tool_input.file_path, .tool_input.notebook_path] | map(select(. != null))[] | ., "\u0000"' <<<"${input}")
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
# points at `.env` reads the env file. A relative link target is resolved
# against the directory of the link, and a leading `~/` against $HOME. If the
# chain cannot be followed (readlink fails, or more than 40 hops, which is also
# what a symlink loop looks like), the call is blocked.
check_path() {
  local current="$1" target dir hop tilde='~'
  for ((hop = 0; hop < 40; hop++)); do
    [[ "${current}" == "${tilde}/"* ]] && current="${HOME}/${current#"${tilde}/"}"
    if is_env_file "${current}"; then
      block "${current##*/} is an env file. Real env files hold secrets and stay off-limits; the example files (.env.example, .env.*.example, .env.sample, .env.template) are allowed. Ask the user to read or change it."
    fi
    [[ -L "${current}" ]] || return 0
    target="$(readlink "${current}")" || block "could not follow the symlink ${current}. Refusing to run unchecked."
    if [[ "${target}" != /* ]]; then
      dir="."
      [[ "${current}" == */* ]] && dir="${current%/*}"
      target="${dir}/${target}"
    fi
    current="${target}"
  done
  block "symlink chain from ${1} is longer than 40 hops or loops. Refusing to run unchecked."
}

for one in "${paths[@]}"; do
  check_path "${one}"
done

exit 0
