#!/usr/bin/env bash
# PostToolUse hook for Edit|Write: tells Claude when a .json file it just
# wrote no longer parses.
#
# Exit 2 is how a PostToolUse hook reaches Claude: stderr is shown to it. The
# edit has already happened, so nothing is blocked. Every other path exits 0;
# a problem in this hook must never get in Claude's way.
#
# The file path comes from .tool_input.file_path on stdin. The inline version
# this replaces read $CLAUDE_FILE_PATH, which Claude Code does not set, so it
# never ran.

file="$(jq -r '.tool_input.file_path // empty' 2>/dev/null)"
[[ "${file}" == *.json && -f "${file}" ]] || exit 0

# JSON-with-comments files: jq rejects them by design.
case "${file##*/}" in
  tsconfig*.json | jsconfig*.json | devcontainer.json) exit 0 ;;
esac
case "${file}" in
  */.vscode/*) exit 0 ;;
esac

if ! err="$(jq empty "${file}" 2>&1)"; then
  echo "Warning: ${file} is not valid JSON: ${err}" >&2
  exit 2
fi
exit 0
