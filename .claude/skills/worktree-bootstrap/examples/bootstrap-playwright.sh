#!/usr/bin/env bash
# Orca Setup Script for a worktree of a Playwright E2E repo: copies the
# gitignored env file from the main checkout, installs deps and Chromium.
#
#   bash <workspace>/my-dev-things/setup/bootstrap-worktree-e2e.sh
#
# The env file holds test credentials, so it is copied, never read, printed
# or rebuilt. When the main checkout has none, nothing is created, so the
# Playwright config still fails with its own message.
# Safe to re-run.
set -euo pipefail

REPO_NAME="e2e"
NOTES_DIR="my-dev-things"
ENV_NAME=".env.dev"

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
cd "$REPO_DIR"

copy_from_main "$MAIN_CHECKOUT" "$REPO_DIR" "$ENV_NAME" --optional

link_workspace_context "$REPO_DIR" "$(workspace_root "$MAIN_CHECKOUT")" "$NOTES_DIR"

use_repo_node "$REPO_DIR"
if [ -d node_modules ]; then
  log "node_modules/ already present, skipping install"
else
  corepack pnpm install --frozen-lockfile
fi

corepack pnpm exec playwright install chromium

log "bootstrap done. Run a spec with: corepack pnpm exec playwright test <file>"
