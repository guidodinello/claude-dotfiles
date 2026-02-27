#!/bin/bash
# Moves a ~/.claude/* file into this repo and creates a symlink back.
# Usage: ./add_file.sh ~/.claude/agents/my-agent.md
#        ./add_file.sh ~/.claude/skills/my-skill/SKILL.md

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DST="${HOME}/.claude"

file_path="${1}"

if [ -z "${file_path}" ]; then
    echo "Usage: $0 <path-to-claude-file>"
    echo "Examples:"
    echo "  $0 ~/.claude/agents/my-agent.md"
    echo "  $0 ~/.claude/skills/my-skill/SKILL.md"
    echo "  $0 ~/.claude/hooks/my-hook.sh"
    exit 1
fi

# Expand ~ in path
file_path="${file_path/#\~/$HOME}"

if [ ! -f "${file_path}" ]; then
    echo "File not found: ${file_path}"
    exit 1
fi

if [[ "${file_path}" != "${CLAUDE_DST}"/* ]]; then
    echo "Error: file must be inside ~/.claude/ — got: ${file_path}"
    exit 1
fi

rel="${file_path#"${CLAUDE_DST}"/}"
dst="${DOTFILES_DIR}/.claude/${rel}"
dst_dir="$(dirname "${dst}")"

mkdir -p "${dst_dir}"
mv "${file_path}" "${dst}"
ln -s "${dst}" "${file_path}"

echo "Added: ~/.claude/${rel} → repo (.claude/${rel})"
echo "Remember to: git add .claude/${rel} && git commit"
