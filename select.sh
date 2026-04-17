#!/bin/bash
# Interactive selector — symlink a subset of .claude/ items into ~/.claude/
# Requires fzf for the best experience; falls back to a plain numbered menu.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
CLAUDE_DST="${HOME}/.claude"

GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[1;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
header()   { echo -e "\n${BOLD}${CYAN}=== $* ===${NC}"; }

if [ ! -d "${CLAUDE_SRC}" ]; then
    echo "No .claude/ directory found in repo — nothing to do."
    exit 0
fi

# ---------------------------------------------------------------------------
# Build candidate list
# Each entry is "category/name" — for skill/agent dirs that's the dir itself;
# for flat files (hooks, guidelines, scripts, settings) it's the file path.
# ---------------------------------------------------------------------------
declare -a CANDIDATES

collect_dirs() {
    local category="$1"
    local base="${CLAUDE_SRC}/${category}"
    [ -d "${base}" ] || return
    for entry in "${base}"/*/; do
        [ -d "${entry}" ] && CANDIDATES+=("${category}/$(basename "${entry}")")
    done
}

collect_files() {
    local category="$1"
    local base="${CLAUDE_SRC}/${category}"
    [ -d "${base}" ] || return
    while IFS= read -r -d '' f; do
        rel="${f#"${CLAUDE_SRC}"/}"
        CANDIDATES+=("${rel}")
    done < <(find "${base}" -type f -print0 | sort -z)
}

collect_flat() {
    local base="${CLAUDE_SRC}"
    while IFS= read -r -d '' f; do
        [ -d "${f}" ] && continue
        rel="${f#"${base}"/}"
        # skip anything already handled as a dir-based category
        local top
        top="$(echo "${rel}" | cut -d/ -f1)"
        case "${top}" in skills|agents|hooks|guidelines|scripts) continue ;; esac
        CANDIDATES+=("${rel}")
    done < <(find "${base}" -maxdepth 1 -type f -print0 | sort -z)
}

collect_dirs  "skills"
collect_files "agents"
collect_files "hooks"
collect_files "guidelines"
collect_files "scripts"
collect_flat

if [ ${#CANDIDATES[@]} -eq 0 ]; then
    echo "No items found to select."
    exit 0
fi

# ---------------------------------------------------------------------------
# Selection UI
# ---------------------------------------------------------------------------
select_with_fzf() {
    printf '%s\n' "${CANDIDATES[@]}" | \
        fzf --multi \
            --prompt="Pick items to symlink (TAB=toggle, ENTER=confirm): " \
            --header="Space/TAB to select, ENTER to confirm" \
            --layout=reverse
}

select_plain() {
    header "Available items"
    local i=1
    for item in "${CANDIDATES[@]}"; do
        printf "  %3d) %s\n" "${i}" "${item}"
        (( i++ ))
    done
    echo
    echo "Enter numbers separated by spaces (e.g. 1 3 5), or 'all':"
    read -r input
    if [ "${input}" = "all" ]; then
        printf '%s\n' "${CANDIDATES[@]}"
        return
    fi
    for n in ${input}; do
        if [[ "${n}" =~ ^[0-9]+$ ]] && (( n >= 1 && n <= ${#CANDIDATES[@]} )); then
            echo "${CANDIDATES[$((n-1))]}"
        else
            log_warn "Ignoring invalid selection: ${n}"
        fi
    done
}

header "Select items to install"

if command -v fzf &>/dev/null; then
    mapfile -t SELECTED < <(select_with_fzf)
else
    echo "(fzf not found — using plain menu)"
    mapfile -t SELECTED < <(select_plain)
fi

if [ ${#SELECTED[@]} -eq 0 ]; then
    echo "Nothing selected — exiting."
    exit 0
fi

# ---------------------------------------------------------------------------
# Symlink selected items
# ---------------------------------------------------------------------------
link_file() {
    local src="$1"
    local rel="${src#"${CLAUDE_SRC}"/}"
    local target="${CLAUDE_DST}/${rel}"
    local target_dir
    target_dir="$(dirname "${target}")"

    mkdir -p "${target_dir}"

    if [ -L "${target}" ]; then
        log_warn "Already a symlink, skipping: ~/.claude/${rel}"
        return
    elif [ -f "${target}" ]; then
        log_warn "Backing up existing file: ~/.claude/${rel} → ${target}.bak"
        mv "${target}" "${target}.bak"
    fi

    ln -s "${src}" "${target}"
    log_info "Linked: ~/.claude/${rel}"
}

header "Linking selected items"

for item in "${SELECTED[@]}"; do
    src="${CLAUDE_SRC}/${item}"
    if [ -d "${src}" ]; then
        # Link all files inside the directory
        while IFS= read -r -d '' f; do
            link_file "${f}"
        done < <(find "${src}" -type f -print0)
    elif [ -f "${src}" ]; then
        link_file "${src}"
    else
        log_warn "Not found, skipping: ${item}"
    fi
done

# Ensure hooks are executable
find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true

echo
log_info "Done! Run ./select.sh again to add more items."
