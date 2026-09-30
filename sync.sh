#!/bin/bash
# Dotfiles sync
# Symlinks config files from this repo into a Claude config directory, and
# merges the shared settings base into that directory's settings.json.
# Safe to re-run any time to pick up new/updated files after a `git pull`.
#
# Usage:
#   ./sync.sh                     # sync ~/.claude plus every existing ~/.claude-* profile
#   ./sync.sh ~/.claude-work      # sync only that CLAUDE_CONFIG_DIR
#
# settings.json is NOT symlinked: it is generated per config dir by merging
# settings.base.json with the keys Claude Code writes at runtime, so each dir
# keeps its own autoMode/enabledPlugins state instead of sharing one file.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
OPENCODE_SRC="${DOTFILES_DIR}/.config/opencode"
OPENCODE_DST="${HOME}/.config/opencode"

# Never symlinked into a config dir.
#   settings.json       - generated below, per config dir
#   settings.base.json  - source for that merge, not a file Claude Code reads
#   settings.local.json - project-scoped; Claude Code reads it from a project's
#                         .claude/, not from a user config dir
SKIP_FILES=("settings.json" "settings.base.json" "settings.local.json")

# Keys owned by the config dir, not the repo. Claude Code writes these at
# runtime (learned auto-mode environment, plugin toggles); a sync must not
# clobber them, and they must not leak between the personal and work dirs.
LOCAL_KEYS=("autoMode" "enabledPlugins")

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()  { echo -e "${RED}[ERR ]${NC}  $*"; }

command -v jq >/dev/null 2>&1 || { log_err "jq is required but not installed."; exit 1; }

symlink_tree() {
    local src="$1" dst="$2" label="$3" apply_skips="$4"

    if [ ! -d "${src}" ]; then
        log_warn "No ${label}/ directory found - skipping."
        return
    fi

    while IFS= read -r -d '' file; do
        rel="${file#"${src}"/}"

        if [ "${apply_skips}" = "skip" ]; then
            local skip=""
            for s in "${SKIP_FILES[@]}"; do
                [ "${rel}" = "${s}" ] && skip="yes" && break
            done
            [ -n "${skip}" ] && continue
        fi

        target="${dst}/${rel}"
        mkdir -p "$(dirname "${target}")"

        if [ -L "${target}" ]; then
            continue
        elif [ -f "${target}" ]; then
            log_warn "Backing up existing file: ${label}/${rel} -> ${target}.bak"
            mv "${target}" "${target}.bak"
        fi

        ln -s "${file}" "${target}"
        log_info "Linked: ${label}/${rel}"
    done < <(find "${src}" -type f -print0)
}

# Merge settings.base.json into <dst>/settings.json, preserving LOCAL_KEYS from
# whatever is already there. {{CONFIG_DIR}} resolves to the destination dir so
# each config dir points at its own symlinked scripts.
merge_settings() {
    local dst="$1"
    local base="${CLAUDE_SRC}/settings.base.json"
    local current="${dst}/settings.json"

    if [ ! -f "${base}" ]; then
        log_warn "No settings.base.json - skipping settings merge."
        return
    fi

    # Read the local keys FIRST: in the old layout this path is a symlink into
    # the repo, and Claude Code wrote runtime keys back through it. Reading
    # follows the link; removing it before reading would discard that state.
    local local_json="{}"
    if [ -f "${current}" ]; then
        if ! jq empty "${current}" 2>/dev/null; then
            log_err "${current} is not valid JSON - refusing to overwrite it."
            return 1
        fi
        local filter=""
        for k in "${LOCAL_KEYS[@]}"; do
            filter="${filter}${filter:+,}\"${k}\""
        done
        local_json="$(jq "{${filter}} | with_entries(select(.value != null))" "${current}")"
    fi

    # Now drop the legacy symlink so the generated file is real and per-dir.
    if [ -L "${current}" ]; then
        log_warn "Replacing legacy settings.json symlink with a generated file"
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        rm "${current}"
    fi

    local merged
    merged="$(jq -n \
        --argjson base "$(sed "s|{{CONFIG_DIR}}|${dst}|g" "${base}")" \
        --argjson local "${local_json}" \
        '$base * $local')"

    if [ -f "${current}" ] && [ "$(jq -S . <<<"${merged}")" = "$(jq -S . "${current}")" ]; then
        log_info "settings.json already up to date"
        return
    fi

    if [ -f "${current}" ]; then
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backed up previous settings.json"
    fi

    printf '%s\n' "${merged}" > "${current}"
    log_info "Merged settings.json (preserved: ${LOCAL_KEYS[*]})"
}

# With an explicit target, sync only that dir. Otherwise sync every
# CLAUDE_CONFIG_DIR profile on this machine: the default ~/.claude plus any
# alternate profile dirs already set up (e.g. the `claude-work` alias's
# CLAUDE_CONFIG_DIR=~/.claude-work). Alternates are only synced if the
# directory already exists, so this never creates a profile the user hasn't
# set up on this machine.
CLAUDE_DSTS=()
if [ -n "${1:-}" ]; then
    mkdir -p "$1"
    CLAUDE_DSTS+=("$(cd "$1" && pwd)")
else
    mkdir -p "${HOME}/.claude"
    CLAUDE_DSTS+=("${HOME}/.claude")
    for alt in "${HOME}"/.claude-*; do
        [ -d "${alt}" ] && CLAUDE_DSTS+=("${alt}")
    done
fi

for CLAUDE_DST in "${CLAUDE_DSTS[@]}"; do
    log_info "Target config dir: ${CLAUDE_DST}"
    symlink_tree "${CLAUDE_SRC}" "${CLAUDE_DST}" "$(basename "${CLAUDE_DST}")" "skip"
    merge_settings "${CLAUDE_DST}"
    find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
done

# opencode lives at a fixed path, not per profile; sync it once, on runs
# that include the default ~/.claude.
if [ "${CLAUDE_DSTS[0]}" = "${HOME}/.claude" ]; then
    symlink_tree "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "no-skip"
fi

log_info "Done! Claude Code tools are ready in: ${CLAUDE_DSTS[*]}"
