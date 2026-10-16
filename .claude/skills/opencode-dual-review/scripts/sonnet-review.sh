#!/usr/bin/env bash
# Fallback reviewer for when the free opencode models time out or fail: one Claude Sonnet
# run at low effort, fed the exact prompt dual-review.sh builds, from a fresh detached
# worktree so the implementer's worktree is never touched. Posts in the same format.
#
# Usage: sonnet-review.sh <repo-dir> <pr-number> [diff-base-ref]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${1:?usage: sonnet-review.sh <repo-dir> <pr-number>}" && pwd)"
PR_NUMBER="${2:?usage: sonnet-review.sh <repo-dir> <pr-number>}"
DIFF_BASE="${3:-}"
MODEL_LABEL="claude-sonnet (low effort)"

WT="$(mktemp -d)/review-pr-$PR_NUMBER"
git -C "$REPO_DIR" fetch origin --quiet
git -C "$REPO_DIR" worktree add --detach "$WT" origin/HEAD >/dev/null 2>&1 \
  || git -C "$REPO_DIR" worktree add --detach "$WT" >/dev/null
cleanup() { git -C "$REPO_DIR" worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT

PROMPT_FILE="$(MAX_DIFF_LINES="${MAX_DIFF_LINES:-20000}" PROMPT_ONLY=1 PR_CHECKOUT_DETACH=1 "$SCRIPT_DIR/dual-review.sh" "$WT" "$PR_NUMBER" $DIFF_BASE | tail -1)"
OUT_FILE="$(dirname "$PROMPT_FILE")/review_sonnet.txt"
echo "Prompt: $PROMPT_FILE" >&2

(cd "$WT" && claude -p --model sonnet --effort low --tools "" --strict-mcp-config \
  --setting-sources "" --no-session-persistence < "$PROMPT_FILE" > "$OUT_FILE" 2>&1)

if ! grep -q -e 'NO_FINDINGS' -e '---FINDING-START---' "$OUT_FILE"; then
  echo "Sonnet returned no verdict; nothing posted. Raw output: $OUT_FILE" >&2
  exit 1
fi
if ! python3 -I "$SCRIPT_DIR/post_structured_review.py" "$REPO_DIR" "$PR_NUMBER" "$MODEL_LABEL" "$OUT_FILE" >&2; then
  echo "ERROR: posting the Sonnet review to PR #$PR_NUMBER failed; findings are in $OUT_FILE" >&2
  exit 1
fi
echo "posted Sonnet review to PR #$PR_NUMBER ($OUT_FILE)" >&2
