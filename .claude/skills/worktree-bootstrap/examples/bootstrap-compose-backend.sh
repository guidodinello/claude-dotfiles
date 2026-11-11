#!/usr/bin/env bash
# Orca Setup Script for a worktree of a Node API that runs under docker
# compose: its own compose project and host ports, env copied from the main
# checkout, deps installed, stack up and migrated. Tracked files untouched.
#
#   bash <workspace>/my-dev-things/setup/bootstrap-worktree-backend.sh
#
# Safe to re-run: ports are chosen once and kept while the env file is
# already isolated. Adapt the CONFIG block, the override and the commands.
set -euo pipefail

# --- CONFIG -----------------------------------------------------------------
REPO_NAME="backend"
NOTES_DIR="my-dev-things"
PROJECT_PREFIX="proj-"          # every worktree compose project starts with it
MAIN_COMPOSE_PROJECT="backend"  # the main checkout's project, never touched
PORT_BASE_API=31000             # bases at least 1000 apart (offsets are 1..899)
PORT_BASE_DB=32000
PORT_BASE_ADMIN_UI=33000
CONTAINER_API_PORT=3000
HEALTH_PATH="/health"
MIGRATE_CMD=(pnpm run migration:up)
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
PROJECT="$(compose_project_name "$PROJECT_PREFIX" "$WORKTREE_NAME")"
assert_worktree_project "$PROJECT" "$PROJECT_PREFIX" "$MAIN_COMPOSE_PROJECT"
ENV_FILE="$REPO_DIR/.env"
OVERRIDE_FILE="docker-compose.override.yml"

copy_from_main "$MAIN_CHECKOUT" "$REPO_DIR" ".env"

if [ "$(get_env_key "$ENV_FILE" COMPOSE_PROJECT_NAME)" = "$PROJECT" ] \
  && has_env_key "$ENV_FILE" WORKTREE_PORT_OFFSET; then
  log ".env already isolated as '$PROJECT', keeping its ports"
else
  OFFSET="$(pick_free_offset "$WORKTREE_NAME" "$PORT_BASE_API" "$PORT_BASE_DB" "$PORT_BASE_ADMIN_UI")"
  set_env_key "$ENV_FILE" COMPOSE_PROJECT_NAME "$PROJECT"
  set_env_key "$ENV_FILE" WORKTREE_PORT_OFFSET "$OFFSET"
  set_env_key "$ENV_FILE" WORKTREE_API_PORT "$((PORT_BASE_API + OFFSET))"
  set_env_key "$ENV_FILE" FORWARD_DB_PORT "$((PORT_BASE_DB + OFFSET))"
  set_env_key "$ENV_FILE" WORKTREE_ADMIN_UI_PORT "$((PORT_BASE_ADMIN_UI + OFFSET))"
  log "isolated as '$PROJECT' with port offset +$OFFSET"
fi

fill_missing_env_keys "$ENV_FILE" "$REPO_DIR/.env.example"

API_PORT="$(get_env_key "$ENV_FILE" WORKTREE_API_PORT)"
ADMIN_UI_PORT="$(get_env_key "$ENV_FILE" WORKTREE_ADMIN_UI_PORT)"

# The base compose file hardcodes host ports, so they are replaced here
# (`!override` needs a Compose release that supports merge tags). The scheduler
# would run jobs against external services with the copied credentials, and
# the admin UI is heavy, so both sit behind profiles in worktrees.
! is_tracked "$REPO_DIR" "$OVERRIDE_FILE" || die "$OVERRIDE_FILE is tracked in this repo; adapt this script"
cat >"$OVERRIDE_FILE" <<EOF
services:
  app:
    ports: !override
      - "${API_PORT}:${CONTAINER_API_PORT}"
  admin-ui:
    profiles: [admin-ui]
    ports: !override
      - "${ADMIN_UI_PORT}:3000"
  scheduler:
    profiles: [scheduler]
EOF
ensure_git_exclude "$REPO_DIR" "/$OVERRIDE_FILE"
log "wrote $OVERRIDE_FILE; scheduler and admin-ui are off (enable with --profile scheduler / --profile admin-ui)"

link_workspace_context "$REPO_DIR" "$(workspace_root "$MAIN_CHECKOUT")" "$NOTES_DIR"

use_repo_node "$REPO_DIR"
if [ -d node_modules ]; then
  log "node_modules/ already present, skipping install"
else
  corepack pnpm install --frozen-lockfile
fi

wait_for_docker
log "bringing up compose project '$PROJECT'..."
docker compose -p "$PROJECT" up -d --build

API_URL="http://localhost:${API_PORT}"
log "waiting for ${API_URL}${HEALTH_PATH}..."
if ! wait_for_http "${API_URL}${HEALTH_PATH}" 360; then
  docker compose -p "$PROJECT" logs --tail 30 app >&2 || true
  die "API did not become healthy on port $API_PORT"
fi

log "running migrations..."
docker compose -p "$PROJECT" exec -T app "${MIGRATE_CMD[@]}"

log "bootstrap done: API $API_URL (compose project $PROJECT)"
