# shellcheck shell=bash
# Helpers for per-repo worktree bootstrap scripts. Source it, never run it.
#
# Installed at ~/.claude/skills/worktree-bootstrap/lib.sh by the dotfiles sync.
# It holds no project constants and derives nothing from its own location:
# every project value (prefixes, port bases, repo names) is an argument.
#
# Needs bash 3.2+, git 2.31+, awk, grep, cksum. Port helpers need lsof, the
# Docker helpers need docker, the HTTP helpers need curl, the Node helper nvm.

log() { echo "==> $*"; }
warn() { echo "==> WARNING: $*" >&2; }
die() {
  echo "==> ERROR: $*" >&2
  exit 1
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' is required but not on PATH"
  done
}

# --- worktree identity ------------------------------------------------------

# Orca passes the new worktree as $ORCA_WORKTREE_PATH; a manual run uses $PWD.
worktree_dir() {
  local dir="${ORCA_WORKTREE_PATH:-$PWD}"
  [ -d "$dir" ] || die "worktree path '$dir' does not exist"
  git -C "$dir" rev-parse --show-toplevel 2>/dev/null || die "'$dir' is not inside a git work tree"
}

# A bare --git-common-dir is relative to the caller's cwd, hence --path-format.
main_checkout() {
  local common
  common="$(git -C "$1" rev-parse --path-format=absolute --git-common-dir)" || die "cannot resolve the git common dir of '$1'"
  dirname "$common"
}

is_main_checkout() {
  local dir="$1" main
  main="$(main_checkout "$dir")"
  [ "$(cd "$dir" && pwd -P)" = "$(cd "$main" && pwd -P)" ]
}

# Usage: require_worktree <dir> [expected-main-checkout-basename]
require_worktree() {
  local dir="$1" expected="${2:-}" main
  main="$(main_checkout "$dir")"
  if [ -n "$expected" ] && [ "$(basename "$main")" != "$expected" ]; then
    die "'$dir' is not a worktree of '$expected' (its main checkout is '$main')"
  fi
  ! is_main_checkout "$dir" || die "'$dir' is the main checkout; worktree bootstraps only run in worktrees"
}

# Repos are cloned as subdirectories of the workspace, so the workspace is the
# main checkout's parent unless WORKTREE_WORKSPACE_ROOT says otherwise.
workspace_root() {
  echo "${WORKTREE_WORKSPACE_ROOT:-$(dirname "$1")}"
}

# Usage: paired_worktree <main-checkout> <sibling-repo-name> <worktree-name> [required-file]
# Prints the sibling repo's worktree with the same directory name, or nothing.
paired_worktree() {
  local main="$1" sibling="$2" name="$3" required="${4:-}" sibling_main path
  sibling_main="$(dirname "$main")/$sibling"
  [ -d "$sibling_main" ] || return 0
  git -C "$sibling_main" worktree list --porcelain | awk '/^worktree /{ print substr($0, 10) }' |
    while IFS= read -r path; do
      [ "$path" != "$sibling_main" ] || continue
      [ "$(basename "$path")" = "$name" ] || continue
      if [ -z "$required" ] || [ -f "$path/$required" ]; then
        echo "$path"
        break
      fi
    done
}

# --- names and ports --------------------------------------------------------

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-'
}

# Human-readable on purpose: `docker ps` must trace a container back to its worktree.
compose_project_name() {
  echo "$1$(slugify "$2")"
}

# Usage: assert_worktree_project <project> <prefix> [main-project]
assert_worktree_project() {
  local project="$1" prefix="$2" main_project="${3:-}"
  [ -n "$prefix" ] || die "a worktree compose project prefix is required"
  if [ -n "$main_project" ] && [ "$project" = "$main_project" ]; then
    die "refusing to touch compose project '$project' (the main checkout's stack)"
  fi
  case "$project" in
    "$prefix"*) ;;
    *) die "compose project '$project' does not start with '$prefix'; refusing" ;;
  esac
}

# 1..899, stable for a given name. Space port bases at least 1000 apart.
port_offset() {
  echo $(($(printf '%s' "$1" | cksum | cut -d' ' -f1) % 899 + 1))
}

port_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

offset_ports_free() {
  local off="$1" base
  shift
  for base in "$@"; do
    port_listening $((base + off)) && return 1
  done
  return 0
}

# Usage: pick_free_offset <worktree-name> <port-base>...
# Starts from the name's offset and walks forward only past ports already
# taken, so record the result instead of recomputing it elsewhere.
pick_free_offset() {
  local name="$1" off tries=0
  shift
  [ "$#" -gt 0 ] || die "pick_free_offset needs at least one port base"
  require_cmd lsof
  off="$(port_offset "$name")"
  while ! offset_ports_free "$off" "$@"; do
    off=$((off % 899 + 1))
    tries=$((tries + 1))
    [ "$tries" -lt 899 ] || die "no free port offset found"
  done
  echo "$off"
}

# --- env files (values are never printed except by get_env_key) -------------

# Prints the value. Only call it for keys the bootstrap owns (ports, project
# names, URLs), never for secrets.
get_env_key() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 0
  awk -v k="$key" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }' "$file"
}

has_env_key() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  awk -v k="$key" 'index($0, k "=") == 1 { found = 1; exit } END { exit !found }' "$file"
}

# Rewrites in place through a temp file, so the file keeps its mode. The value
# travels through the environment, so '/', '&', '\' and '$' stay literal.
set_env_key() {
  local file="$1" key="$2" value="$3" tmp
  if has_env_key "$file" "$key"; then
    tmp="$(mktemp)"
    WB_KEY="$key" WB_VALUE="$value" awk '
      index($0, ENVIRON["WB_KEY"] "=") == 1 { print ENVIRON["WB_KEY"] "=" ENVIRON["WB_VALUE"]; next }
      { print }
    ' "$file" >"$tmp"
    cat "$tmp" >"$file"
    rm -f "$tmp"
  else
    if [ -s "$file" ] && [ -n "$(tail -c1 "$file")" ]; then
      echo >>"$file"
    fi
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

delete_env_key() {
  local file="$1" key="$2" tmp
  has_env_key "$file" "$key" || return 0
  tmp="$(mktemp)"
  awk -v k="$key" 'index($0, k "=") != 1' "$file" >"$tmp"
  cat "$tmp" >"$file"
  rm -f "$tmp"
}

# Appends every key the example defines and the env file lacks, with the
# example's default. Never touches an existing key; prints key names only.
fill_missing_env_keys() {
  local env_file="$1" example="$2" missing
  if [ ! -f "$example" ]; then
    log "no $(basename "$example") to fill missing keys from"
    return 0
  fi
  missing="$(awk -F= '
    NR == FNR { if ($0 ~ /^[A-Za-z_][A-Za-z0-9_]*=/) have[$1] = 1; next }
    /^[A-Za-z_][A-Za-z0-9_]*=/ && !($1 in have) { print }
  ' "$env_file" "$example")"
  if [ -z "$missing" ]; then
    log "$(basename "$env_file") has every key in $(basename "$example")"
    return 0
  fi
  {
    echo ""
    echo "# Added from $(basename "$example") by the worktree bootstrap on $(date +%Y-%m-%d)"
    echo "$missing"
  } >>"$env_file"
  log "added to $(basename "$env_file") from $(basename "$example"): $(echo "$missing" | cut -d= -f1 | paste -sd ' ' -)"
}

# Usage: copy_from_main <main-checkout> <worktree> <relative-path> [--optional]
# Copies without reading the file. Never overwrites. A missing source dies,
# or only warns with --optional (no empty file is created either way, so the
# tool that needs it still fails with its own message).
copy_from_main() {
  local main="$1" dir="$2" name="$3" optional="${4:-}"
  if [ -e "$dir/$name" ]; then
    log "$name already present, leaving it alone"
    return 0
  fi
  if [ ! -s "$main/$name" ]; then
    [ "$optional" = "--optional" ] || die "no $name in the main checkout ($main); create it there first"
    warn "no $name in the main checkout ($main); create it there, then re-run this bootstrap"
    return 0
  fi
  mkdir -p "$(dirname "$dir/$name")"
  cp "$main/$name" "$dir/$name"
  chmod 600 "$dir/$name"
  log "$name copied from the main checkout"
}

# --- git-local state --------------------------------------------------------

is_tracked() {
  git -C "$1" ls-files --error-unmatch -- "$2" >/dev/null 2>&1
}

# info/exclude lives in the common git dir, shared by every worktree, so
# concurrent bootstraps take a lock before appending.
ensure_git_exclude() {
  local dir="$1" pattern="$2" common exclude lock tries=0
  common="$(git -C "$dir" rev-parse --path-format=absolute --git-common-dir)"
  exclude="$common/info/exclude"
  lock="$common/info/exclude.lock.d"
  mkdir -p "$common/info"
  touch "$exclude"
  until mkdir "$lock" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -lt 50 ] || break
    sleep 0.2
  done
  grep -qxF "$pattern" "$exclude" || echo "$pattern" >>"$exclude"
  rmdir "$lock" 2>/dev/null || true
}

# Usage: skip_worktree <dir> <path>...
# For tracked files that local tooling rewrites on every run. The flag is per
# worktree; undo with `git update-index --no-skip-worktree <path>`.
skip_worktree() {
  local dir="$1" file
  shift
  git -C "$dir" ls-files -- "$@" | while IFS= read -r file; do
    git -C "$dir" update-index --skip-worktree -- "$file"
  done
}

# Usage: link_excluded <worktree> <target> <link-name>
# Symlinks <target> into the worktree and hides it through info/exclude.
# Never replaces a real file or a tracked path.
link_excluded() {
  local dir="$1" target="$2" name="$3"
  if [ ! -e "$target" ]; then
    warn "$target not found, not linking $name"
    return 0
  fi
  if [ -e "$dir/$name" ] && [ ! -L "$dir/$name" ]; then
    warn "$dir/$name exists and is not a symlink, leaving it alone"
    return 0
  fi
  if is_tracked "$dir" "$name"; then
    warn "$name is tracked in this repo, not linking over it"
    return 0
  fi
  ln -sfn "$target" "$dir/$name"
  ensure_git_exclude "$dir" "/$name"
  log "linked $name -> $target (ignored via info/exclude)"
}

# Usage: link_workspace_context <worktree> <workspace-root> [notes-dir-name]
# Worktrees live outside the workspace, so a Claude Code session there misses
# the workspace CLAUDE.md and the private notes. CLAUDE.local.md is loaded by
# Claude Code itself. The notes get a dot name because tools with broad globs
# (a tsconfig `include` of `**/*.ts`, test runners) follow a plain-name link
# and compile or collect whatever the notes contain.
# A missing CLAUDE.md dies: a worktree without it silently loses every
# workspace rule (reviews then check compliance against nothing).
link_workspace_context() {
  local dir="$1" ws="$2" notes="${3:-my-dev-things}"
  [ -f "$ws/CLAUDE.md" ] || die "workspace CLAUDE.md not found at $ws/CLAUDE.md (set WORKTREE_WORKSPACE_ROOT if the workspace is not the main checkout's parent)"
  link_excluded "$dir" "$ws/CLAUDE.md" "CLAUDE.local.md"
  link_excluded "$dir" "$ws/$notes" ".$notes"
}

# --- runtimes and services --------------------------------------------------

# Activates the repo's .nvmrc Node through nvm. nvm.sh is not safe under
# `set -eu`, so both are lifted around it.
use_repo_node() {
  local dir="$1" nvm_dir="${NVM_DIR:-$HOME/.nvm}" rc=0
  export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
  export COREPACK_ENABLE_AUTO_PIN=0
  if [ ! -f "$dir/.nvmrc" ]; then
    command -v node >/dev/null 2>&1 || die "no .nvmrc in $dir and no node on PATH"
    log "no .nvmrc, using node $(node -v) from PATH"
    return 0
  fi
  [ -s "$nvm_dir/nvm.sh" ] || die "$dir/.nvmrc needs nvm, not found at $nvm_dir"
  set +eu
  # shellcheck disable=SC1091
  . "$nvm_dir/nvm.sh"
  (cd "$dir" && nvm install >/dev/null) && nvm use --silent "$(cat "$dir/.nvmrc")" >/dev/null || rc=$?
  set -eu
  [ "$rc" -eq 0 ] || die "nvm could not activate $dir/.nvmrc"
  log "node $(node -v)"
}

docker_ready() {
  docker info >/dev/null 2>&1
}

# Usage: wait_for_docker [timeout-seconds]
# Starts Docker Desktop on macOS; elsewhere it only waits for the daemon.
wait_for_docker() {
  local timeout="${1:-120}" waited=0
  docker_ready && return 0
  if [ "$(uname -s)" = "Darwin" ]; then
    log "starting Docker Desktop..."
    open -a Docker || true
  else
    log "waiting for the Docker daemon..."
  fi
  while [ "$waited" -lt "$timeout" ]; do
    docker_ready && {
      log "Docker is ready"
      return 0
    }
    sleep 3
    waited=$((waited + 3))
  done
  die "Docker did not become ready within ${timeout}s"
}

http_code() {
  curl -s -o /dev/null -m 5 -w '%{http_code}' "$1" 2>/dev/null || true
}

# Usage: wait_for_http <url> [timeout-seconds] [expected-code]
wait_for_http() {
  local url="$1" timeout="${2:-300}" expected="${3:-200}" waited=0
  while [ "$waited" -lt "$timeout" ]; do
    [ "$(http_code "$url")" = "$expected" ] && return 0
    sleep 5
    waited=$((waited + 5))
  done
  return 1
}
