#!/bin/bash
# Moves a ~/.claude/* file or directory into this repo, stages it, and creates file-level symlinks back.
# Usage: ./add_file.sh ~/.claude/agents/my-agent.md
#        ./add_file.sh ~/.claude/skills/my-skill
#        ./add_file.sh ~/.claude/hooks/my-hook.sh

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DST="${HOME}/.claude"

# shellcheck source=lib/link.sh
source "${DOTFILES_DIR}/lib/link.sh"

file_path="${1}"

if [ -z "${file_path}" ]; then
    echo "Usage: $0 <path-to-claude-file-or-dir>"
    echo "Examples:"
    echo "  $0 ~/.claude/agents/my-agent.md"
    echo "  $0 ~/.claude/skills/my-skill"
    echo "  $0 ~/.claude/hooks/my-hook.sh"
    exit 1
fi

# Expand ~ in path
file_path="${file_path/#\~/$HOME}"
# Strip trailing slash so path handling is consistent
file_path="${file_path%/}"

if [ ! -e "${file_path}" ]; then
    echo "Not found: ${file_path}"
    exit 1
fi

if [[ "${file_path}" != "${CLAUDE_DST}"/* ]]; then
    echo "Error: path must be inside ~/.claude/ — got: ${file_path}"
    exit 1
fi

rel="${file_path#"${CLAUDE_DST}"/}"
dst="${DOTFILES_DIR}/.claude/${rel}"

# sync.sh generates or skips these per config dir; moving one into the repo
# would replace the generated file with a stale copy.
if is_skipped "${rel}"; then
    echo "Error: ${rel} is generated or skipped by sync.sh and cannot be added to the repo"
    exit 1
fi

# A symlink here is already linked (probably into this repo): moving it would
# put a link to itself in the repo.
if [ -L "${file_path}" ]; then
    echo "Error: ${file_path} is a symlink to $(readlink "${file_path}"); nothing to add"
    exit 1
fi

if [ -e "${dst}" ]; then
    echo "Error: already exists in the repo: ${dst}"
    exit 1
fi

mkdir -p "$(dirname "${dst}")"
mv "${file_path}" "${dst}"

# Link it back, and into every other config dir on this machine, the same
# way sync.sh would on its next run. The item is not tracked yet, so it is
# linked from disk and then staged: the next sync links tracked files only.
while IFS= read -r dir; do
    link_under "${DOTFILES_DIR}/.claude" "${dst}" "${dir}" skip any
done < <(config_dirs)
# An existing profile without the marker is not in that list; say so.
warn_unmarked_config_dirs

stage_in_repo "${DOTFILES_DIR}" "${rel}"
echo "Remember to commit: git commit -m \"feat: add ${rel}\""
