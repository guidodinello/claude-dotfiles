#!/bin/bash
# Claude Code dotfiles setup
# Symlinks all .claude/ files from this repo into ~/.claude/

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
CLAUDE_DST="${HOME}/.claude"

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

symlink_tree "${CLAUDE_SRC}" "${CLAUDE_DST}" ".claude"

# Ensure hooks are executable
find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

log_info "Done! Claude Code tools are ready."
