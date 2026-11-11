#!/usr/bin/env bash
# Orca Archive Script for a worktree of the compose backend: removes the
# worktree's compose project (containers, named volumes, orphans, locally
# built images). Never touches the main checkout's project.
#
#   bash <workspace>/my-dev-things/setup/teardown-worktree-backend.sh
#
# Orca runs it only on `orca worktree rm --run-hooks`, while the worktree
# still exists. Cleanup must never block the removal, so it always exits 0.
set -uo pipefail

PROJECT_PREFIX="proj-"
MAIN_COMPOSE_PROJECT="backend"

LIB="${WORKTREE_BOOTSTRAP_LIB:-$HOME/.claude/skills/worktree-bootstrap/lib.sh}"
[ -r "$LIB" ] || {
  echo "==> WARNING: $LIB not found, skipping teardown. Install the worktree-bootstrap skill or set WORKTREE_BOOTSTRAP_LIB." >&2
  exit 0
}
# shellcheck source-path=SCRIPTDIR source=../lib.sh
. "$LIB"

main() {
  local dir="${ORCA_WORKTREE_PATH:-$PWD}" project
  if [ ! -d "$dir" ]; then
    warn "$dir does not exist (already removed?), nothing to tear down"
    return 0
  fi
  if is_main_checkout "$dir" 2>/dev/null; then
    warn "$dir is the main checkout; refusing"
    return 0
  fi

  # The env file holds the name compose actually used, even after a rename.
  project="$(get_env_key "$dir/.env" COMPOSE_PROJECT_NAME)"
  [ -n "$project" ] || project="$(compose_project_name "$PROJECT_PREFIX" "$(basename "$dir")")"
  if [ "$project" = "$MAIN_COMPOSE_PROJECT" ] || [[ "$project" != "$PROJECT_PREFIX"* ]]; then
    warn "compose project '$project' is not a worktree project; refusing"
    return 0
  fi

  if ! docker_ready; then
    warn "Docker is not running, skipping teardown of $project"
    return 0
  fi

  log "tearing down compose project '$project'..."
  (cd "$dir" && docker compose -p "$project" down -v --remove-orphans --rmi local) ||
    warn "docker compose down failed for $project (see output above)"
  log "teardown attempt done for $project"
}

main || true
exit 0
