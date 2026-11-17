#!/bin/bash
# Dotfiles sync
# Symlinks config files from this repo into a Claude config directory, and
# merges the shared settings base into that directory's settings.json.
# Safe to re-run any time to pick up new/updated files after a `git pull`.
#
# Usage:
#   ./sync.sh                     # sync ~/.claude plus every existing ~/.claude-* profile
#   ./sync.sh ~/.claude-work      # sync only that CLAUDE_CONFIG_DIR
#
# settings.json is NOT symlinked: it is generated per config dir by merging
# settings.base.json with the keys Claude Code writes at runtime, so each dir
# keeps its own autoMode/enabledPlugins state instead of sharing one file.

set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_SRC="${DOTFILES_DIR}/.claude"
OPENCODE_SRC="${DOTFILES_DIR}/.config/opencode"
OPENCODE_DST="${HOME}/.config/opencode"

# Never symlinked into a config dir.
#   settings.json       - generated below, per config dir
#   settings.base.json  - source for that merge, not a file Claude Code reads
#   settings.local.json - project-scoped; Claude Code reads it from a project's
#                         .claude/, not from a user config dir
SKIP_FILES=("settings.json" "settings.base.json" "settings.local.json")

# Keys owned by the config dir, not the repo. Claude Code and installers write
# these at runtime (learned auto-mode environment, plugin toggles, the output
# style gentle-ai sets); a sync must not clobber them, and they must not leak
# between the personal and work dirs.
LOCAL_KEYS=("autoMode" "enabledPlugins" "outputStyle")

# Lists that both the repo and installers write to: Orca and herdr register
# hooks, gentle-ai adds engram permissions and secret-file deny rules. Hooks
# (per event) and these permission lists are unioned with the live file instead
# of replaced, so a sync never drops an installer's entry. The cost: removing an
# entry from the base does not remove it from an existing config dir, unless
# its command is listed in RETIRED_HOOK_COMMANDS below.
UNION_PERMISSIONS='["allow","deny","ask","additionalDirectories"]'

# Hook commands that were removed from settings.base.json on purpose. To retire
# a hook, delete it from the base AND add its exact command here: merge_settings
# strips these from the live file before the union, so the old entry is not
# kept next to the new one. Keep entries listed (they are harmless once gone).
#   "rtk hook claude" - its rewrite voids auto-mode verdicts (Issue 389).
RETIRED_HOOK_COMMANDS=("rtk hook claude")
# The two inline Bash guards (Docker volumes, wrangler), replaced by
# hooks/guard-bash.sh: they read .command instead of .tool_input.command and
# used `grep -P`, so they never fired. One command per line, read literally.
while IFS= read -r retired_cmd; do
    RETIRED_HOOK_COMMANDS+=("${retired_cmd}")
done <<'RETIRED'
cmd=$(cat | jq -r '.command // ""'); if echo "$cmd" | grep -qP 'docker\s+(compose|stack)\s+.*\bdown\b.*(-v|--volumes)\b|docker\s+volume\s+(rm|remove|prune)\b'; then echo "BLOCKED: destructive Docker volume command. Volumes hold persistent data and removal is irreversible. Ask the user before running this."; exit 2; fi
cmd=$(cat | jq -r '.command // ""'); if [ -n "$CLOUDFLARE_ENV" ] && echo "$cmd" | grep -qP 'wrangler(\s+|$)'; then echo "BLOCKED: CLOUDFLARE_ENV=$CLOUDFLARE_ENV is set — wrangler may silently target that environment. Unset it and use explicit --env flags instead."; exit 2; fi; if echo "$cmd" | grep -qP 'wrangler(\s+|$)(?=.*d1\s+(?:execute|migrations\s+apply))(?!.*--local)'; then echo "BLOCKED: wrangler d1 execute/migrations apply without --local targets production. Run the command manually with --remote after reviewing."; exit 2; fi
RETIRED

GREEN='\033[1;32m'; YELLOW='\033[1;33m'; RED='\033[1;31m'; NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_err()  { echo -e "${RED}[ERR ]${NC}  $*"; }

command -v jq >/dev/null 2>&1 || { log_err "jq is required but not installed."; exit 1; }

symlink_tree() {
    local src="$1" dst="$2" label="$3" apply_skips="$4"

    if [ ! -d "${src}" ]; then
        log_warn "No ${label}/ directory found - skipping."
        return
    fi

    while IFS= read -r -d '' file; do
        rel="${file#"${src}"/}"

        if [ "${apply_skips}" = "skip" ]; then
            local skip=""
            for s in "${SKIP_FILES[@]}"; do
                [ "${rel}" = "${s}" ] && skip="yes" && break
            done
            [ -n "${skip}" ] && continue
        fi

        target="${dst}/${rel}"
        mkdir -p "$(dirname "${target}")"

        if [ -L "${target}" ]; then
            continue
        elif [ -f "${target}" ]; then
            log_warn "Backing up existing file: ${label}/${rel} -> ${target}.bak"
            mv "${target}" "${target}.bak"
        fi

        ln -s "${file}" "${target}"
        log_info "Linked: ${label}/${rel}"
    done < <(find "${src}" -type f -print0)
}

# Merge settings.base.json into <dst>/settings.json, preserving LOCAL_KEYS from
# whatever is already there. {{CONFIG_DIR}} resolves to the destination dir so
# each config dir points at its own symlinked scripts.
merge_settings() {
    local dst="$1"
    local base="${CLAUDE_SRC}/settings.base.json"
    local current="${dst}/settings.json"

    if [ ! -f "${base}" ]; then
        log_warn "No settings.base.json - skipping settings merge."
        return
    fi

    # Read the local keys FIRST: in the old layout this path is a symlink into
    # the repo, and Claude Code wrote runtime keys back through it. Reading
    # follows the link; removing it before reading would discard that state.
    local live_json="{}"
    if [ -f "${current}" ]; then
        if ! jq empty "${current}" 2>/dev/null; then
            log_err "${current} is not valid JSON - refusing to overwrite it."
            return 1
        fi
        live_json="$(jq . "${current}")"
    fi
    local local_keys_json
    local_keys_json="$(printf '%s\n' "${LOCAL_KEYS[@]}" | jq -R . | jq -s .)"

    # Now drop the legacy symlink so the generated file is real and per-dir.
    if [ -L "${current}" ]; then
        log_warn "Replacing legacy settings.json symlink with a generated file"
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        rm "${current}"
    fi

    local retired_json
    # select(length > 0): an empty array prints one blank line, which must not
    # become [""] and match every hook that has no command.
    retired_json="$(printf '%s\n' "${RETIRED_HOOK_COMMANDS[@]}" | jq -R 'select(length > 0)' | jq -s .)"

    local merged
    merged="$(jq -n \
        --argjson base "$(sed "s|{{CONFIG_DIR}}|${dst}|g" "${base}")" \
        --argjson live "${live_json}" \
        --argjson localKeys "${local_keys_json}" \
        --argjson retired "${retired_json}" \
        --argjson unionPerms "${UNION_PERMISSIONS}" '
        def union($a; $b): reduce ($b // [])[] as $x (($a // []);
            if any(.[]; . == $x) then . else . + [$x] end);
        # Strip retired commands from one event entry. Drop the entry only when
        # the strip emptied it; entries that were already empty, or are not
        # shaped like {hooks: [...]}, pass through untouched.
        def unretire_entry:
            if type == "object" and (.hooks | type) == "array" then
                (.hooks | length) as $n
                | .hooks |= map(select((type == "object" and ((.command // "") | IN($retired[]))) | not))
                | if $n > 0 and (.hooks | length) == 0 then empty else . end
            else . end;
        def unretire:
            if (.hooks | type) == "object" then
                .hooks |= with_entries(.value |= (if type == "array" then map(unretire_entry) else . end))
            else . end;
        ($live | unretire) as $live
        | ($live | with_entries(select(.key as $k | $localKeys | index($k)))
               | with_entries(select(.value != null))) as $own
        | ($base * $own)
        | .hooks = (reduce ((($base.hooks // {}) + ($live.hooks // {})) | keys[]) as $ev
            ({}; .[$ev] = union($base.hooks[$ev]; $live.hooks[$ev])))
        | reduce $unionPerms[] as $p (.;
            (union($base.permissions[$p]; $live.permissions[$p])) as $u
            | if ($u | length) > 0 then .permissions[$p] = $u else . end)
        | if .hooks == {} then del(.hooks) else . end')"

    if [ -f "${current}" ] && [ "$(jq -S . <<<"${merged}")" = "$(jq -S . "${current}")" ]; then
        log_info "settings.json already up to date"
        return
    fi

    if [ -f "${current}" ]; then
        cp "${current}" "${current}.bak-$(date +%Y%m%d-%H%M%S)"
        log_warn "Backed up previous settings.json"
    fi

    printf '%s\n' "${merged}" > "${current}"
    log_info "Merged settings.json (preserved: ${LOCAL_KEYS[*]})"
}

# With an explicit target, sync only that dir. Otherwise sync every
# CLAUDE_CONFIG_DIR profile on this machine: the default ~/.claude plus any
# alternate profile dirs already set up (e.g. the `claude-work` alias's
# CLAUDE_CONFIG_DIR=~/.claude-work). Alternates are only synced if the
# directory already exists, so this never creates a profile the user hasn't
# set up on this machine.
CLAUDE_DSTS=()
if [ -n "${1:-}" ]; then
    mkdir -p "$1"
    CLAUDE_DSTS+=("$(cd "$1" && pwd)")
else
    mkdir -p "${HOME}/.claude"
    CLAUDE_DSTS+=("${HOME}/.claude")
    for alt in "${HOME}"/.claude-*; do
        [ -d "${alt}" ] && CLAUDE_DSTS+=("${alt}")
    done
fi

for CLAUDE_DST in "${CLAUDE_DSTS[@]}"; do
    log_info "Target config dir: ${CLAUDE_DST}"
    symlink_tree "${CLAUDE_SRC}" "${CLAUDE_DST}" "$(basename "${CLAUDE_DST}")" "skip"
    merge_settings "${CLAUDE_DST}"
    find "${CLAUDE_DST}/hooks" -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
done

# opencode lives at a fixed path, not per profile; sync it once, on runs
# that include the default ~/.claude.
if [ "${CLAUDE_DSTS[0]}" = "${HOME}/.claude" ]; then
    symlink_tree "${OPENCODE_SRC}" "${OPENCODE_DST}" ".config/opencode" "no-skip"
fi

log_info "Done! Claude Code tools are ready in: ${CLAUDE_DSTS[*]}"
