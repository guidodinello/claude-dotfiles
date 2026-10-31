#!/usr/bin/env bash
# Review a PR: opencode-dual-review first (1 attempt per model, 8 min budget), then one
# Claude Sonnet review (medium effort) if both opencode slots post nothing. Diffs over
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
  # Measure the PR's head, not whatever the caller has checked out.
  git -C "$REPO_DIR" fetch --quiet origin "pull/$PR_NUMBER/head"
  lines=$(git -C "$REPO_DIR" diff "$DIFF_BASE"...FETCH_HEAD | wc -l)
else
  lines=$(cd "$REPO_DIR" && gh pr diff "$PR_NUMBER" | wc -l)
fi
echo "PR #$PR_NUMBER diff: $lines lines" >&2

# The opencode slots are off by default (2026-10-27): opencode v2.1.4's `execute`
# tool runs model-written JavaScript with full fs access, and no permission or
# tools key in the locked config stops it. Until the slots are isolated, every
# review goes to the no-tools Sonnet path. OPENCODE_SLOTS=1 re-enables them.
if [[ "${OPENCODE_SLOTS:-0}" != 1 ]]; then
  echo "opencode slots disabled (OPENCODE_SLOTS!=1): straight to Sonnet" >&2
  exec "$SCRIPT_DIR/sonnet-review.sh" "$REPO_DIR" "$PR_NUMBER" ${DIFF_BASE:+"$DIFF_BASE"}
fi

if (( lines > SONNET_DIRECT_LINES )); then
  echo "over $SONNET_DIRECT_LINES lines: straight to Sonnet" >&2
  exec "$SCRIPT_DIR/sonnet-review.sh" "$REPO_DIR" "$PR_NUMBER" ${DIFF_BASE:+"$DIFF_BASE"}
fi

WT="$(mktemp -d)/review-pr-$PR_NUMBER"
git -C "$REPO_DIR" worktree add --detach "$WT" >/dev/null
status=0
out="$(PR_CHECKOUT_DETACH=1 "$SCRIPT_DIR/dual-review.sh" "$WT" "$PR_NUMBER" ${DIFF_BASE:+"$DIFF_BASE"} 2>&1)" || status=$?
git -C "$REPO_DIR" worktree remove --force "$WT" >/dev/null 2>&1 || true

# No RESULTS section: dual-review.sh stopped before reviewing (unknown diff base,
# failed checkout, ...). Show why and fail instead of exiting 0 with nothing posted.
if ! grep -q "=== RESULTS ===" <<<"$out"; then
  echo "$out" >&2
  echo "dual-review.sh stopped before reviewing (status $status); nothing posted" >&2
  exit "$(( status == 0 ? 1 : status ))"
fi
echo "$out" | grep -E "Output dir|succeeded|exhausted|budget|posted" >&2 || true

if echo "$out" | grep -q "Slot A -> model: none" && echo "$out" | grep -q "Slot B -> model: none"; then
  echo "both opencode slots empty: falling back to Sonnet" >&2
  exec "$SCRIPT_DIR/sonnet-review.sh" "$REPO_DIR" "$PR_NUMBER" ${DIFF_BASE:+"$DIFF_BASE"}
fi
