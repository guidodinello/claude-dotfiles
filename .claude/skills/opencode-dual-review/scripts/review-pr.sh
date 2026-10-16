#!/usr/bin/env bash
# Review a PR: opencode-dual-review first (1 attempt per model, 8 min budget), then one
# Claude Sonnet low-effort review if both opencode slots post nothing. Diffs over
# SONNET_DIRECT_LINES go straight to Sonnet: the free models never finish at that size.
# Runs from a fresh detached worktree, so the implementer's worktree may be dirty.
#
# Usage: review-pr.sh <repo-dir> <pr-number> [diff-base-ref]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${1:?usage: review-pr.sh <repo-dir> <pr-number>}" && pwd)"
PR_NUMBER="${2:?usage: review-pr.sh <repo-dir> <pr-number>}"
DIFF_BASE="${3:-}"
SONNET_DIRECT_LINES="${SONNET_DIRECT_LINES:-1500}"

if [[ -n "$DIFF_BASE" ]]; then
  lines=$(git -C "$REPO_DIR" diff "$DIFF_BASE"...HEAD | wc -l)
else
  lines=$(cd "$REPO_DIR" && gh pr diff "$PR_NUMBER" | wc -l)
fi
echo "PR #$PR_NUMBER diff: $lines lines" >&2

if (( lines > SONNET_DIRECT_LINES )); then
  echo "over $SONNET_DIRECT_LINES lines: straight to Sonnet" >&2
  exec "$SCRIPT_DIR/sonnet-review.sh" "$REPO_DIR" "$PR_NUMBER" $DIFF_BASE
fi

WT="$(mktemp -d)/review-pr-$PR_NUMBER"
git -C "$REPO_DIR" worktree add --detach "$WT" >/dev/null
out="$(PR_CHECKOUT_DETACH=1 "$SCRIPT_DIR/dual-review.sh" "$WT" "$PR_NUMBER" $DIFF_BASE 2>&1 || true)"
git -C "$REPO_DIR" worktree remove --force "$WT" >/dev/null 2>&1 || true
echo "$out" | grep -E "Output dir|succeeded|exhausted|budget|posted" >&2 || true

if echo "$out" | grep -q "Slot A -> model: none" && echo "$out" | grep -q "Slot B -> model: none"; then
  echo "both opencode slots empty: falling back to Sonnet" >&2
  exec "$SCRIPT_DIR/sonnet-review.sh" "$REPO_DIR" "$PR_NUMBER" $DIFF_BASE
fi
