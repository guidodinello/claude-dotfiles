#!/bin/bash
# Workaround for gentle-ai refusing to read symlinked agent config files.
# Tracks https://github.com/Gentleman-Programming/gentle-ai/issues/306
#
# Swap symlinks -> real copies, run gentle-ai install, merge written files
# back into this repo, restore symlinks. Safe to re-run any time.
#
# Usage: ./update-gentle-ai.sh [gentle-ai install args...]

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DST="${HOME}/.claude"
STASH_DIR="$(mktemp -d /tmp/gentle-ai-update.XXXXXX)"

# Files gentle-ai backs up/restores during install. Add more if the
# installer starts managing other symlinked files.
MANAGED_FILES=(CLAUDE.md settings.json)

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err() { echo -e "${RED}[ERR]${NC}  $*"; }

SWAPPED=()
dotfiles_source() {
    local name="$1"
    if [ -L "${CLAUDE_DST}/${name}" ]; then
        readlink "${CLAUDE_DST}/${name}" 2>/dev/null || true
    elif [ -e "${DOTFILES_DIR}/.claude/${name}" ]; then
        echo "${DOTFILES_DIR}/.claude/${name}"
    fi
}

swap_in() {
    local name="$1"
    local src
    src="$(dotfiles_source "${name}")"
    if [ -z "${src}" ]; then
        log_warn "${name}: not symlinked and not in repo — leaving as-is."
        return
    fi
    cp "${src}" "${STASH_DIR}/${name}.orig"
    if [ -L "${CLAUDE_DST}/${name}" ]; then
        unlink "${CLAUDE_DST}/${name}"
        cp "${src}" "${CLAUDE_DST}/${name}"
        SWAPPED+=("${name}")
        log_info "${name}: swapped symlink -> real copy (source: repo/relative)"
    fi
}

restore() {
    local name="$1"
    local src
    src="$(dotfiles_source "${name}")"
    [ -z "${src}" ] && return
    unlink "${CLAUDE_DST}/${name}"
    ln -s "${src}" "${CLAUDE_DST}/${name}"
    log_info "${name}: symlink restored."
}

trap 'for f in "${SWAPPED[@]}"; do dotfiles_source "$f" >/dev/null 2>&1 && restore "$f"; done' EXIT

if ! command -v gentle-ai >/dev/null 2>&1; then
    log_err "gentle-ai not found on PATH."
    exit 1
fi

for f in "${MANAGED_FILES[@]}"; do
    swap_in "$f"
done

log_info "Running: gentle-ai install $*"
gentle-ai install "$@"

for f in "${SWAPPED[@]}"; do
    if ! jq -e . "${CLAUDE_DST}/${f}" >/dev/null 2>&1 && [[ "${f}" == *.json ]]; then
        log_err "${f} is not valid JSON after install — skipping merge-back."
        exit 1
    fi
    src="$(dotfiles_source "${f}")"
    cp "${CLAUDE_DST}/${f}" "${src}"
    log_info "${f}: merged written file into dotfiles."
    if diff -q "${STASH_DIR}/${f}.orig" "${src}" >/dev/null 2>&1; then
        log_info "${f}: no changes from the update."
    else
        log_warn "${f}: update changed the file (${STASH_DIR}/${f}.orig has the pre-update copy)."
    fi
done

log_info "Done. Backups in ${STASH_DIR}"