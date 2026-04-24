#!/usr/bin/env bash
# Moves a skill/agent/file from any project's .claude/ into this repo and symlinks it globally.
# Usage: ./promote.sh [--delete-original] <path-inside-any-.claude/>
# Examples:
#   ./promote.sh /path/to/project/.claude/skills/my-skill
#   ./promote.sh ~/.claude/agents/my-agent.md
#   ./promote.sh --delete-original /path/to/project/.claude/hooks/my-hook.sh

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_CLAUDE="${HOME}/.claude"
DELETE_ORIGINAL=false

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

if [[ "${1}" == "--delete-original" ]]; then
    DELETE_ORIGINAL=true
    shift
fi

src="${1}"

if [[ -z "${src}" ]]; then
    echo "Usage: $0 [--delete-original] <path-to-item-in-any-.claude/>"
    echo "Examples:"
    echo "  $0 /path/to/project/.claude/skills/my-skill"
    echo "  $0 ~/.claude/agents/my-agent.md"
    echo "  $0 --delete-original /path/to/project/.claude/hooks/my-hook.sh"
    exit 1
fi

# Expand ~
src="${src/#\~/$HOME}"

if [[ ! -e "${src}" ]]; then
    echo "Not found: ${src}"
    exit 1
fi

# Require path to be inside a .claude/ directory
if [[ "${src}" != *"/.claude/"* ]]; then
    echo "Error: path must be inside a .claude/ directory — got: ${src}"
    exit 1
fi

# Guard: already in this repo
if [[ "${src}" == "${DOTFILES_DIR}/.claude/"* ]]; then
    echo "Already in repo: ${src}"
    exit 1
fi

# Extract the .claude/ root and relative path within it
# e.g. /proj/.claude/skills/foo  →  claude_root=/proj/.claude  rel=skills/foo
claude_root="${src%%/.claude/*}/.claude"
rel="${src#"${claude_root}"/}"

repo_dst="${DOTFILES_DIR}/.claude/${rel}"
global_link="${GLOBAL_CLAUDE}/${rel}"
is_from_global=false
[[ "${claude_root}" == "${GLOBAL_CLAUDE}" ]] && is_from_global=true

# Guard: destination in repo already exists
if [[ -e "${repo_dst}" ]]; then
    echo "Already exists in repo: ${repo_dst}"
    exit 1
fi

mkdir -p "$(dirname "${repo_dst}")"

# Move item (file or directory) to repo
mv "${src}" "${repo_dst}"
log_info "Moved to repo: .claude/${rel}"

# Create file-level global symlinks (consistent with setup.sh approach)
_link_item() {
    local item="${1}"
    local item_rel="${item#"${DOTFILES_DIR}/.claude/"}"
    local link="${GLOBAL_CLAUDE}/${item_rel}"

    mkdir -p "$(dirname "${link}")"

    if [[ -L "${link}" ]]; then
        log_warn "Already a symlink, skipping: ~/.claude/${item_rel}"
    elif [[ -e "${link}" ]]; then
        log_warn "Backing up existing file: ~/.claude/${item_rel} → ${link}.bak"
        mv "${link}" "${link}.bak"
        ln -s "${item}" "${link}"
        log_info "Linked: ~/.claude/${item_rel}"
    else
        ln -s "${item}" "${link}"
        log_info "Linked: ~/.claude/${item_rel}"
    fi
}

if [[ -d "${repo_dst}" ]]; then
    while IFS= read -r -d '' file; do
        _link_item "${file}"
    done < <(find "${repo_dst}" -type f -print0)
else
    _link_item "${repo_dst}"
fi

# Report on original project location
if ! $is_from_global; then
    if $DELETE_ORIGINAL; then
        log_info "Original removed (item was moved, --delete-original acknowledged)"
    else
        log_warn "Original path is now empty: ${src}"
        log_warn "Safe to remove: rm -rf \"${src}\""
    fi
fi

echo ""
log_info "Remember to: git add .claude/${rel} && git commit"
