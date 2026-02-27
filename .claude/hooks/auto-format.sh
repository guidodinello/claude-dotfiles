#!/bin/bash
# ~/.claude/hooks/auto-format.sh
#
# Global auto-formatter hook for PostToolUse (Edit|Write).
# Zero Claude tokens — runs as a pure side effect.
#
# Resolution order:
#   1. Project-local override: $PROJECT_ROOT/.claude/hooks/auto-format.sh
#   2. Heuristic detection using local binaries (no npx, no script aliases)
#
# Always exits 0 — formatter failures must never block Claude.

# ── Resolve project root ────────────────────────────────────────────────────
# CLAUDE_PROJECT_DIR is set by Claude Code in hook context.
# Fall back to git root, then cwd, so the script degrades gracefully.
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
  ROOT="$CLAUDE_PROJECT_DIR"
elif git rev-parse --show-toplevel &>/dev/null; then
  ROOT="$(git rev-parse --show-toplevel)"
else
  ROOT="$(pwd)"
fi

# ── Option A: project-local override ────────────────────────────────────────
PROJECT_HOOK="$ROOT/.claude/hooks/auto-format.sh"
if [ -f "$PROJECT_HOOK" ]; then
  exec bash "$PROJECT_HOOK"
fi

# ── Read hook input ──────────────────────────────────────────────────────────
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[ -z "$FILE" ] && exit 0
[ ! -f "$FILE" ] && exit 0  # file may have been deleted

EXT="${FILE##*.}"

# ── Option B: heuristic detection via local binaries ────────────────────────
# Prefer local binaries over npx to avoid spawning a fresh Node process.
# Never call project-specific script aliases (pnpm run fixer, sail, etc.)
# — those may not exist and behave differently across projects.

BIN="$ROOT/node_modules/.bin"
VENDOR="$ROOT/vendor/bin"

case "$EXT" in

  ts|tsx|js|jsx)
    if [ -x "$BIN/eslint" ]; then
      "$BIN/eslint" --fix "$FILE" --quiet 2>/dev/null
    fi
    ;;

  css|scss)
    if [ -x "$BIN/prettier" ]; then
      "$BIN/prettier" --write "$FILE" --loglevel silent 2>/dev/null
    fi
    ;;

  php)
    if [ -x "$VENDOR/pint" ]; then
      "$VENDOR/pint" "$FILE" --quiet 2>/dev/null
    elif [ -x "$VENDOR/php-cs-fixer" ]; then
      "$VENDOR/php-cs-fixer" fix "$FILE" --quiet 2>/dev/null
    fi
    ;;

  json|yaml|yml)
    if [ -x "$BIN/prettier" ]; then
      "$BIN/prettier" --write "$FILE" --loglevel silent 2>/dev/null
    fi
    ;;

esac

exit 0
