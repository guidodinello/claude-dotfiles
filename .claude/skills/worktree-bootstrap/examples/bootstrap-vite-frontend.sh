#!/usr/bin/env bash
# Orca Setup Script for a worktree of a Vite frontend that pairs with the
# backend worktree of the same directory name.
#
#   bash <workspace>/my-dev-things/setup/bootstrap-worktree-frontend.sh
#
# Pairing: VITE_API_URL points at the backend worktree named like this one
# when it exists (its recorded WORKTREE_API_PORT), otherwise at the main
# checkout's API. Create the backend worktree first, or re-run this after it
# and restart Vite. The dev port reuses the paired backend's recorded offset.
# Safe to re-run: only VITE_API_URL, and VITE_APP_URL while it is a plain
# localhost URL, are ever rewritten.
set -euo pipefail

# --- CONFIG -----------------------------------------------------------------
REPO_NAME="frontend"
BACKEND_REPO_NAME="backend"
NOTES_DIR="my-dev-things"
PORT_BASE_DEV=35000   # one base per frontend repo, 1000 apart from the backend's
MAIN_API_PORT=3000
API_PATH="/api"
# ----------------------------------------------------------------------------

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

WORKTREE_NAME="$(basename "$REPO_DIR")"
ENV_FILE="$REPO_DIR/.env"

copy_from_main "$MAIN_CHECKOUT" "$REPO_DIR" ".env"
fill_missing_env_keys "$ENV_FILE" "$REPO_DIR/.env.example"

PAIRED="$(paired_worktree "$MAIN_CHECKOUT" "$BACKEND_REPO_NAME" "$WORKTREE_NAME" ".env")"
if [ -n "$PAIRED" ]; then
  API_PORT="$(get_env_key "$PAIRED/.env" WORKTREE_API_PORT)"
  OFFSET="$(get_env_key "$PAIRED/.env" WORKTREE_PORT_OFFSET)"
  [ -n "$API_PORT" ] || die "paired backend $PAIRED has no WORKTREE_API_PORT; run its bootstrap first"
  log "paired with backend worktree $PAIRED"
else
  API_PORT="$MAIN_API_PORT"
  OFFSET=""
  log "no $BACKEND_REPO_NAME worktree named '$WORKTREE_NAME', pointing at the main API"
fi
[ -n "$OFFSET" ] || OFFSET="$(port_offset "$WORKTREE_NAME")"
DEV_PORT=$((PORT_BASE_DEV + OFFSET))

set_env_key "$ENV_FILE" VITE_API_URL "http://localhost:${API_PORT}${API_PATH}"
log "VITE_API_URL=http://localhost:${API_PORT}${API_PATH}"

if grep -Eq '^VITE_APP_URL=https?://localhost(:[0-9]+)?/?$' "$ENV_FILE"; then
  set_env_key "$ENV_FILE" VITE_APP_URL "http://localhost:${DEV_PORT}"
  log "VITE_APP_URL=http://localhost:${DEV_PORT}"
fi

link_workspace_context "$REPO_DIR" "$(workspace_root "$MAIN_CHECKOUT")" "$NOTES_DIR"

use_repo_node "$REPO_DIR"
if [ -d node_modules ]; then
  log "node_modules/ already present, skipping install"
else
  corepack pnpm install --frozen-lockfile
fi

log "bootstrap done. Start Vite with: corepack pnpm dev --port ${DEV_PORT} --strictPort"
