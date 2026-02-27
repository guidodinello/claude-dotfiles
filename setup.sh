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

if [ ! -d "${CLAUDE_SRC}" ]; then
    echo "No .claude/ directory found in repo — nothing to do."
    exit 0
fi

while IFS= read -r -d '' file; do
    rel="${file#"${CLAUDE_SRC}"/}"
    target="${CLAUDE_DST}/${rel}"
    target_dir="$(dirname "${target}")"

    mkdir -p "${target_dir}"

    if [ -L "${target}" ]; then
        log_warn "Already a symlink, skipping: ~/.claude/${rel}"
        continue
    elif [ -f "${target}" ]; then
        log_warn "Backing up existing file: ~/.claude/${rel} → ${target}.bak"
        mv "${target}" "${target}.bak"
    fi

    ln -s "${file}" "${target}"
    log_info "Linked: ~/.claude/${rel}"
done < <(find "${CLAUDE_SRC}" -type f -print0)

# Ensure hooks are executable
find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

log_info "Done! Claude Code tools are ready."
