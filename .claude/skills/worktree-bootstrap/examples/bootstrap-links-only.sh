#!/usr/bin/env bash
# Orca Setup Script for a repo that needs no runtime in its worktrees (infra,
# docs): links the workspace context and nothing else.
#
#   bash <workspace>/my-dev-things/setup/bootstrap-worktree-<repo>.sh
#
# Safe to re-run.
set -euo pipefail

REPO_NAME="infra"
NOTES_DIR="my-dev-things"

LIB="${WORKTREE_BOOTSTRAP_LIB:-$HOME/.claude/skills/worktree-bootstrap/lib.sh}"
[ -r "$LIB" ] || {
  echo "==> ERROR: $LIB not found. Install the worktree-bootstrap skill (dotfiles ./sync.sh) or set WORKTREE_BOOTSTRAP_LIB." >&2
  exit 1
}
# shellcheck source-path=SCRIPTDIR source=../lib.sh
. "$LIB"

REPO_DIR="$(worktree_dir)"
require_worktree "$REPO_DIR" "$REPO_NAME"
MAIN_CHECKOUT="$(main_checkout "$REPO_DIR")"

link_workspace_context "$REPO_DIR" "$(workspace_root "$MAIN_CHECKOUT")" "$NOTES_DIR"
log "bootstrap done"
