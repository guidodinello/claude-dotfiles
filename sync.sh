#!/bin/bash
# Dotfiles sync
# Symlinks config files from this repo into their home-directory locations.
# Safe to re-run any time to pick up new/updated files after a `git pull`.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
OPENCODE_SRC="${DOTFILES_DIR}/.config/opencode"
OPENCODE_DST="${HOME}/.config/opencode"

# Every CLAUDE_CONFIG_DIR profile on this machine gets the same guidelines/rules/skills —
# the default ~/.claude, plus any alternate profile dirs already set up (e.g. the
# `claude-work` alias's CLAUDE_CONFIG_DIR=~/.claude-work). Only synced if the directory
# already exists, so this never creates a profile the user hasn't set up on this machine.
CLAUDE_DSTS=("${HOME}/.claude")
for alt in "${HOME}"/.claude-*; do
    [ -d "${alt}" ] && CLAUDE_DSTS+=("${alt}")
done

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

symlink_tree() {
    local src="$1"
    local dst="$2"
    local label="$3"

    if [ ! -d "${src}" ]; then
        log_warn "No ${label}/ directory found — skipping."
        return
    fi

    while IFS= read -r -d '' file; do
        rel="${file#"${src}"/}"
        target="${dst}/${rel}"
        target_dir="$(dirname "${target}")"

        mkdir -p "${target_dir}"

        if [ -L "${target}" ]; then
            log_warn "Already a symlink, skipping: ~/${label}/${rel}"
            continue
        elif [ -f "${target}" ]; then
            log_warn "Backing up existing file: ~/${label}/${rel} → ${target}.bak"
            mv "${target}" "${target}.bak"
        fi

        ln -s "${file}" "${target}"
        log_info "Linked: ~/${label}/${rel}"
    done < <(find "${src}" -type f -print0)
}

for CLAUDE_DST in "${CLAUDE_DSTS[@]}"; do
    symlink_tree "${CLAUDE_SRC}" "${CLAUDE_DST}" "$(basename "${CLAUDE_DST}")"
    # Ensure hooks are executable
    find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
done
symlink_tree "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode"

log_info "Done! Claude Code tools are ready."
