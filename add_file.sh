#!/bin/bash
# Moves a ~/.claude/* file or directory into this repo and creates file-level symlinks back.
# Usage: ./add_file.sh ~/.claude/agents/my-agent.md
#        ./add_file.sh ~/.claude/skills/my-skill
#        ./add_file.sh ~/.claude/hooks/my-hook.sh

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DST="${HOME}/.claude"

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

mkdir -p "$(dirname "${dst}")"
mv "${file_path}" "${dst}"

# Create file-level symlinks (consistent with setup.sh approach)
if [ -d "${dst}" ]; then
    while IFS= read -r -d '' f; do
        f_rel="${f#"${DOTFILES_DIR}/.claude/"}"
        link="${CLAUDE_DST}/${f_rel}"
        mkdir -p "$(dirname "${link}")"
        ln -s "${f}" "${link}"
        echo "Added: ~/.claude/${f_rel} → repo (.claude/${f_rel})"
    done < <(find "${dst}" -type f -print0)
else
    ln -s "${dst}" "${file_path}"
    echo "Added: ~/.claude/${rel} → repo (.claude/${rel})"
fi

echo "Remember to: git add .claude/${rel} && git commit"
