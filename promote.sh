#!/usr/bin/env bash
# Moves a skill/agent/file from any project's .claude/ into this repo and symlinks it globally.
# Usage: ./promote.sh <path-inside-any-.claude/>
# (--delete-original is still accepted but deprecated and ignored: the item is always moved.)
# Examples:
#   ./promote.sh /path/to/project/.claude/skills/my-skill
#   ./promote.sh ~/.claude/agents/my-agent.md

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_CLAUDE="${HOME}/.claude"
DELETE_ORIGINAL=false

# shellcheck source=lib/link.sh
source "${DOTFILES_DIR}/lib/link.sh"

if [[ "${1}" == "--delete-original" ]]; then
    DELETE_ORIGINAL=true
    shift
fi

src="${1}"

if [[ -z "${src}" ]]; then
    echo "Usage: $0 <path-to-item-in-any-.claude/>"
    echo "Examples:"
    echo "  $0 /path/to/project/.claude/skills/my-skill"
    echo "  $0 ~/.claude/agents/my-agent.md"
    exit 1
fi

# Expand ~, and drop a trailing slash so a symlink is not seen through.
src="${src/#\~/$HOME}"
src="${src%/}"

if [[ ! -e "${src}" ]]; then
    echo "Not found: ${src}"
    exit 1
fi

# A symlink is not the item: moving it would take the link, not the content,
# and the skill would vanish from where the link points.
if [[ -L "${src}" ]]; then
    echo "Error: ${src} is a symlink to $(readlink "${src}"); promote the target instead"
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

# sync.sh generates or skips these per config dir (settings.json) or reads them
# from a project (settings.local.json); moving one here would take the live file
# and leave nothing linked back.
if is_skipped "${rel}"; then
    echo "Error: ${rel} is generated or skipped by sync.sh and cannot be promoted"
    exit 1
fi

repo_dst="${DOTFILES_DIR}/.claude/${rel}"
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

# Link it into every config dir on this machine, the same way sync.sh would
# on its next run.
while IFS= read -r dir; do
    link_under "${DOTFILES_DIR}/.claude" "${repo_dst}" "${dir}" skip any
done < <(config_dirs)
# An existing profile without the marker is not in that list; say so.
warn_unmarked_config_dirs

# The item is not tracked yet, so it was linked from disk; stage it so the next
# sync (tracked files only) keeps the links.
stage_in_repo "${DOTFILES_DIR}" "${rel}"

if $DELETE_ORIGINAL; then
    log_warn "--delete-original: the item is always moved; this flag does nothing"
fi
if ! $is_from_global; then
    log_info "Moved out of ${claude_root}; commit the removal in that project."
fi

echo ""
log_info "Remember to commit: git commit -m \"feat: add ${rel}\""
